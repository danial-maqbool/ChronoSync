import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { api } from "./utils";

type Identity = {
  cloud: boolean;
  user: { id: string; username: string } | null;
};
const AccountContext = createContext<Identity>({ cloud: false, user: null });
export const useAccount = () => useContext(AccountContext);

export function AccountGate({ children }: { children: ReactNode }) {
  const [identity, setIdentity] = useState<Identity | null>(null);
  const [register, setRegister] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function refresh() {
    setError("");
    try {
      setIdentity(await api<Identity>("/auth/status"));
    } catch {
      setError("The server may be waking up. Please try again in a minute.");
    }
  }
  useEffect(() => {
    void refresh();
    const expired = () => setIdentity({ cloud: true, user: null });
    window.addEventListener("chronosync-signed-out", expired);
    return () => window.removeEventListener("chronosync-signed-out", expired);
  }, []);
  if (identity && (!identity.cloud || identity.user)) {
    return (
      <AccountContext.Provider value={identity}>
        {children}
      </AccountContext.Provider>
    );
  }
  return (
    <main className="account-page">
      <section className="account-card">
        <img src="/favicon.svg" width="48" height="48" alt="" />
        <h1>ChronoSync</h1>
        <p>
          {register
            ? "Your own space for documents, dates, and plans."
            : "Welcome back. Your workspace is waiting."}
        </p>
        {!identity ? (
          <button onClick={refresh}>
            {error ? "Try again" : "Connecting…"}
          </button>
        ) : (
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              setBusy(true);
              setError("");
              const values = Object.fromEntries(new FormData(e.currentTarget));
              try {
                const result = await api<{ user: Identity["user"] }>(
                  register ? "/auth/register" : "/auth/login",
                  values,
                );
                setIdentity({ cloud: true, user: result.user });
              } catch (err) {
                setError((err as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            <label>
              Username
              <input
                name="username"
                autoComplete="username"
                autoCapitalize="none"
                pattern="[a-zA-Z0-9_.-]{3,40}"
                required
                minLength={3}
                maxLength={40}
              />
            </label>
            <label>
              Password
              <input
                name="password"
                type="password"
                autoComplete={register ? "new-password" : "current-password"}
                required
                minLength={12}
                maxLength={128}
              />
            </label>
            {register && (
              <>
                <small>
                  Use at least 12 characters. Save this password in your
                  password manager.
                </small>
                <label>
                  Invitation code
                  <input
                    name="invite_code"
                    type="password"
                    autoComplete="off"
                    required
                  />
                </label>
              </>
            )}
            <button className="primary" disabled={busy}>
              {busy
                ? "Please wait…"
                : register
                  ? "Create my account"
                  : "Sign in"}
            </button>
            <button
              type="button"
              onClick={() => {
                setRegister(!register);
                setError("");
              }}
            >
              {register
                ? "Already have an account? Sign in"
                : "Have an invitation? Create an account"}
            </button>
          </form>
        )}
        {error && <p role="alert">{error}</p>}
        <small>
          Private cloud workspace · AI disabled. Uploaded documents are
          processed on the hosted server. Each account has separate data. Free
          hosting can take a minute to wake.
        </small>
      </section>
    </main>
  );
}

export function AccountActions() {
  const account = useAccount();
  const [changing, setChanging] = useState(false);
  const [message, setMessage] = useState("");
  if (!account.cloud) return null;
  return (
    <section className="account-actions">
      <button onClick={() => setChanging(!changing)}>Change password</button>
      <button
        onClick={async () => {
          try {
            await api("/auth/logout", {});
            window.location.reload();
          } catch (err) {
            setMessage((err as Error).message);
          }
        }}
      >
        Sign out
      </button>
      {changing && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            const form = e.currentTarget;
            try {
              await api("/auth/password", {
                ...Object.fromEntries(new FormData(form)),
                username: account.user?.username,
              });
              form.reset();
              setMessage(
                "Password changed. Other sessions have been signed out.",
              );
              setChanging(false);
            } catch (err) {
              setMessage((err as Error).message);
            }
          }}
        >
          <label>
            Current password
            <input
              name="password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            New password
            <input
              name="new_password"
              type="password"
              autoComplete="new-password"
              minLength={12}
              maxLength={128}
              required
            />
          </label>
          <button>Save password</button>
        </form>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
