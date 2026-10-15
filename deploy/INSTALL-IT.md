# ติดตั้ง Thai Flood Dashboard บน Windows Server + IIS

เอกสารสำหรับทีม IT — ใช้เวลาติดตั้งราว 15–30 นาที

## ระบบทำงานอย่างไร

```
Task Scheduler (ทุก 15 นาที, บัญชี SYSTEM)
  └─ thaiflood-update.bat → ดึงข้อมูลจากหน่วยงาน → เขียน C:\inetpub\wwwroot\flood\index.html + geo\*.json
IIS ─ เสิร์ฟโฟลเดอร์นั้นเป็นไฟล์ static (ไม่ต้องตั้ง FastCGI / ASP.NET / PHP)
```

## สิ่งที่ต้องเตรียม

| รายการ | รายละเอียด |
|---|---|
| Windows Server | 2016 ขึ้นไป, IIS + role **Static Content** (แนะนำ **Static Content Compression**) |
| Python | 3.10 ขึ้นไป จาก python.org — ติ๊ก **Add python.exe to PATH** ตอนติดตั้ง |
| ดิสก์ | ราว 2 GB (ฐานข้อมูลเก็บย้อนหลัง 60 วัน) |
| API key | `GISTDA_API_KEY`, `SPHERE_API_KEY` — **ขอจากเจ้าของโครงการทางช่องทางที่ปลอดภัย** (ไม่อยู่ใน repo) |

### Network — server ต้องออกอินเทอร์เน็ต (HTTPS/443) ไปที่

```
api-v3.thaiwater.net                 ThaiWater (ระดับน้ำ ฝน เขื่อน เรดาร์)
api-gateway.gistda.or.th             GISTDA พื้นที่น้ำท่วมจากดาวเทียม
floodbangkok.bangkok.go.th           กทม. เซนเซอร์น้ำท่วมขัง
earthquake.usgs.gov                  แผ่นดินไหว (USGS)
www.disaster.go.th, www.onwr.go.th   ปภ. / สทนช. (รายงาน/ประกาศ)
data.tmd.go.th                       กรมอุตุฯ (ถ้ามี token)
raw.githubusercontent.com            ขอบเขตจังหวัด/ตำบล (ดาวน์โหลดครั้งแรกครั้งเดียว)
overpass-api.de                      โรงพยาบาล/สถานีตำรวจ/ดับเพลิง จาก OpenStreetMap (เดือนละครั้ง)
overpass.kumi.systems                  (สำรองของ overpass-api.de)
pypi.org, files.pythonhosted.org     ตอนติดตั้ง package
```

ถ้าออกผ่าน proxy ขององค์กร ใส่ `HTTPS_PROXY=http://proxy:port` ในไฟล์ `.env` (task รันเป็น SYSTEM จึงไม่ได้ใช้ proxy ของผู้ใช้)

### เครื่องผู้ใช้ (เบราว์เซอร์) ต้องโหลดได้

`cdnjs.cloudflare.com` (ไลบรารีแผนที่), `basemap.sphere.gistda.or.th` (แผนที่ GISTDA), `*.basemaps.cartocdn.com` (แผนที่สำรอง),
`api-v3.thaiwater.net` (ภาพเรดาร์)

## ขั้นตอนติดตั้ง

1. **วางโค้ด** ที่ `C:\thaiflood\max1` (เลือกทางใดทางหนึ่ง)
   - `git clone https://github.com/maximus77mx/max1.git C:\thaiflood\max1`
   - หรือดาวน์โหลด ZIP จากหน้า repo (Code → Download ZIP) แตกไฟล์แล้วเปลี่ยนชื่อโฟลเดอร์เป็น `C:\thaiflood\max1`

2. **ใส่ API key**: คัดลอก `.env.example` เป็น `.env` แล้วกรอกค่า
   ```
   GISTDA_API_KEY=....
   SPHERE_API_KEY=....
   HTTPS_PROXY=http://proxy:port     (ถ้ามี)
   ```

3. **รันตัวติดตั้ง** — เปิด PowerShell แบบ **Run as Administrator**
   ```powershell
   cd C:\thaiflood\max1
   powershell -ExecutionPolicy Bypass -File deploy\windows\install.ps1
   ```
   สคริปต์จะ: สร้าง Python venv + ติดตั้ง package → สร้าง `C:\inetpub\wwwroot\flood` + วาง `web.config`
   → สร้าง IIS application `/flood` ใต้ Default Web Site → ตั้ง Scheduled Task "Thai flood dashboard" ทุก 15 นาที → รันรอบแรก

   ตัวเลือก: `-WebDir D:\web\flood`, `-Minutes 10`, `-SkipIis` (สร้าง site เอง), `-SkipTask`

4. **เปิดดู** `http://<ชื่อ server>/flood/` แล้วตรวจผลรายแหล่งที่ท้ายไฟล์ `C:\thaiflood\max1\data\update.log`
   ```
   [OK ] thaiwater  obs=5333 ...
   [OK ] gistda     obs=960  ...
   [OK ] bma        obs=254  ...
   ```

5. **Sphere key**: ในหน้าจัดการ key ของ GISTDA sphere เพิ่มชื่อโดเมน/IP ของ server ในช่อง Clients ไม่งั้นแผนที่พื้นหลังจะใช้แผนที่สำรองแทน

## ดูแลระบบ

| เรื่อง | วิธี |
|---|---|
| Log | `data\update.log` (หมุนไฟล์เองเมื่อเกิน ~5 MB) |
| รันด้วยมือ | `deploy\windows\thaiflood-update.bat` |
| ข้อมูลเก่า | ลบอัตโนมัติเมื่อเกิน 60 วัน |
| อัปเดตโปรแกรม | `git pull` (หรือแตก ZIP ใหม่ทับ ยกเว้น `.env` และ `data\`) แล้วรัน `.venv\Scripts\pip install .` |
| หยุดชั่วคราว | Task Scheduler → ปิด task "Thai flood dashboard" |
| สำรองข้อมูล | โฟลเดอร์ `data\` (ฐานข้อมูล SQLite + ไฟล์ดิบ) |

## ปัญหาที่พบบ่อย

| อาการ | สาเหตุ / แก้ไข |
|---|---|
| หน้าเว็บขึ้น แต่แผนที่ตำบลไม่ขึ้น (404 ที่ `geo/*.json`) | IIS ไม่รู้จัก `.json` — ตรวจว่ามี `web.config` ในโฟลเดอร์เว็บ |
| ข้อมูลไม่อัปเดต | ดู Task Scheduler → History และ `data\update.log`; บัญชี SYSTEM ต้องเขียนโฟลเดอร์เว็บได้ |
| ทุกแหล่ง timeout | firewall/proxy — ตรวจรายการโดเมนด้านบน และ `HTTPS_PROXY` ใน `.env` |
| แผนที่พื้นหลังเป็นแบบ CARTO ไม่ใช่ GISTDA | Sphere key ไม่ได้อนุญาตโดเมนของ server |
| `[ERR] gistda ... 401/403` | `GISTDA_API_KEY` ผิดหรือหมดอายุ |

ใช้ Apache/Nginx (Linux) แทนได้: ชี้ DocumentRoot ไปที่โฟลเดอร์ output แล้วตั้ง cron
`*/15 * * * * cd /opt/thaiflood && .venv/bin/thaiflood collect --respect-intervals && .venv/bin/thaiflood dashboard /var/www/flood/index.html`
