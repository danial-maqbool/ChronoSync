import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'e2e',workers:1,timeout:60000,use:{baseURL:'http://127.0.0.1:8765',headless:true,viewport:{width:1440,height:900}},reporter:[['list'],['json',{outputFile:'../docs/validation/playwright.json'}]]});
