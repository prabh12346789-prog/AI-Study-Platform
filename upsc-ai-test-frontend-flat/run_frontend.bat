@echo off
if not exist .env copy .env.example .env >nul
call npm install
call npm run dev
