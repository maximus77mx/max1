# QA Corrective Action — Register & Dashboard

Web App สำหรับ **ลงทะเบียนข้อมูล Corrective Action (CA)** พร้อม **Interactive Dashboard**
รันบน Local Host ได้ทันที · React (Vite) + Express + SQLite · 2 ภาษา ไทย/อังกฤษ
มีระบบ **Login + เชิญผ่านอีเมล + สิทธิ์ 4 ระดับ (Role/Level)**

A full-stack web app to **register Corrective Action records** with an **interactive dashboard**.
Runs entirely on localhost. Thai/English UI. Includes **login, email invites, and 4-level RBAC**.

---

## โครงสร้าง / Structure

```
ca-app/
├─ server/        Express API + SQLite (better-sqlite3)
│  ├─ fields.js   นิยามฟิลด์ CA ทั้ง 38 คอลัมน์ + dropdown lists + SLA matrix
│  ├─ db.js       สร้างตาราง + seed ข้อมูล 90 เคสจาก data/seed.json
│  └─ index.js    REST API (records CRUD + /stats aggregation)
└─ client/        React + Vite + Recharts
   └─ src/
      ├─ App.jsx              layout / nav / i18n
      ├─ components/
      │  ├─ RegisterForm.jsx  ฟอร์มลงทะเบียน CA (จัดกลุ่มตาม workflow)
      │  ├─ RecordsTable.jsx  ทะเบียนทั้งหมด + filter + ค้นหา
      │  ├─ Dashboard.jsx     KPI + กราฟ (สถานะ/Product/Priority/Lever/Overdue Aging)
      │  └─ charts.jsx        กราฟ Recharts
      └─ i18n.js              ข้อความ ไทย/อังกฤษ
```

---

## วิธีติดตั้งและรัน / Setup & Run

ต้องมี **Node.js 18+** ติดตั้งก่อน (https://nodejs.org)

```bash
cd ca-app

# 1) ติดตั้ง dependencies ทั้งหมด (root + server + client)
npm run install:all

# 2) ตั้งค่า Super Admin — คัดลอกไฟล์ตัวอย่างแล้วแก้อีเมล/รหัสผ่าน
cp server/.env.example server/.env
#   แก้ SUPER_ADMIN_EMAIL / SUPER_ADMIN_PASSWORD ในไฟล์ server/.env

# 3) รันแบบ dev (เปิด backend :4000 + frontend :5173 พร้อมกัน)
npm run dev
```

จากนั้นเปิดเบราว์เซอร์ที่ **http://localhost:5173** แล้ว **login ด้วยบัญชี Super Admin** ที่ตั้งไว้ใน `.env`

ครั้งแรกที่รัน ระบบจะสร้างฐานข้อมูล `server/data/ca.db`, seed ข้อมูลตัวอย่าง 90 เคส และสร้างบัญชี Super Admin จาก `.env` ให้อัตโนมัติ

### รันแบบ Production (พอร์ตเดียว)

```bash
npm run build        # build frontend → client/dist
npm start            # Express เสิร์ฟทั้ง API + เว็บ ที่ http://localhost:4000
```

---

## ระบบสิทธิ์ / Login & Roles

**Super Admin** ถูกกำหนดจากไฟล์ `server/.env` เท่านั้น (ไม่สามารถสร้าง/ลบผ่านหน้าเว็บได้)
เมื่อ login แล้ว Super Admin / Admin สามารถ **เชิญผู้ใช้ใหม่ผ่านอีเมล** และ **กำหนด Level** ให้แต่ละคน

| Level | Dashboard | ดูทะเบียน | เพิ่ม | แก้ไข | ลบ | จัดการผู้ใช้ |
|-------|:---------:|:--------:|:----:|:-----:|:--:|:-----------:|
| **Super Admin** (.env) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (ทุกคน) |
| **Admin** | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ (Editor/Viewer) |
| **Editor** | ✓ | ✓ | ✓ | ✓ | — | — |
| **Viewer** | ✓ | ✓ | — | — | — | — |

- Admin เชิญได้เฉพาะ Editor/Viewer · Super Admin เชิญได้ทั้ง Admin/Editor/Viewer
- ปุ่ม/เมนูจะซ่อนอัตโนมัติตามสิทธิ์ และ backend บังคับสิทธิ์อีกชั้น (403 ถ้าไม่มีสิทธิ์)

**การเชิญผ่านอีเมล (Invite)**
- ถ้าตั้งค่า SMTP ใน `.env` → ระบบส่งอีเมลคำเชิญจริง
- ถ้าไม่ตั้ง SMTP → ระบบทำงานแบบ *dev mode*: แสดง "ลิงก์คำเชิญ" ให้ copy ไปส่งเอง (ทำงานทันทีบน localhost)
- ผู้ถูกเชิญเปิดลิงก์ → ตั้งรหัสผ่าน → เข้าใช้งานได้ทันทีตามสิทธิ์ที่กำหนด

## ฟีเจอร์ / Features

**ลงทะเบียน (Register)**
- ฟอร์มครบทั้ง 38 ฟิลด์ จัดกลุ่มตาม workflow: ระบุ → ปัญหา → Containment → Root cause → Action plan → Verify → Close → Status
- Dropdown ตรงตาม LISTS ของ Excel (Level, Source, Product, Error type, Priority, RCA method, Lever, Status, Effective, Sustained ฯลฯ)
- Auto-generate CA ID (เช่น `CA-2026-091`)
- ช่องรายบุคคล (Agent / Sup / N-4 / Section) จะโผล่เมื่อ Level = Individual
- Validation ช่องบังคับ + กัน CA ID ซ้ำ

**Dashboard**
- KPI: ทั้งหมด · Overdue · ครบกำหนดใน 7 วัน · Compliance-critical ที่ยังเปิด · Closed แต่ยังไม่ Sustained · % ปิดตรงเวลา
- กราฟ: แยกตาม Status / Level / Product / Priority / Error type / Lever / Agent-vs-Non-agent
- SLA & Overdue Aging (1–7 / 8–14 / 15–30 / 30+ วัน) + ตารางรายการ overdue

**ทะเบียน (Records)**
- ตารางทั้งหมด + ค้นหา + filter ตาม Status/Level/Product/Priority
- แก้ไข / ลบ รายเคส

---

## หมายเหตุ / Notes

- ฐานข้อมูลเป็นไฟล์เดียว `server/data/ca.db` (SQLite) — สำรองง่าย แค่ copy ไฟล์
- ถ้าอยากล้างข้อมูลกลับไปเป็น seed เดิม: ลบ `server/data/ca.db*` แล้วรันใหม่
- แก้ฟิลด์/dropdown ได้ที่ `server/fields.js` ที่เดียว (ตาราง DB + ฟอร์ม + validation ใช้ร่วมกัน)
