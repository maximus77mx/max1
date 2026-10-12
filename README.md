# thaiflood — เครื่องมือรวบรวมข้อมูลน้ำท่วมประเทศไทย

ดึงข้อมูลแบบ **Realtime** (รายชั่วโมง–รายวัน) จาก 6 หน่วยงาน แปลงให้อยู่ในรูปแบบเดียวกัน
แล้วเก็บสะสมลง SQLite เพื่อใช้เป็นข้อมูล **Historical** พร้อมเก็บ payload ดิบ (JSON/GeoJSON/HTML/ภาพเรดาร์)
ไว้ย้อนดูหรือแปลงใหม่ภายหลัง

| แหล่ง | ชื่อในระบบ | ข้อมูล | รอบเริ่มต้น | ต้องใช้ key |
|---|---|---|---|---|
| ThaiWater.net (สสน.) — **ฐานหลัก** | `thaiwater` | ระดับน้ำแม่น้ำ (m.MSL + ระดับสถานการณ์), ฝน 24 ชม., น้ำในเขื่อน (%) | 1 ชม. | – |
| GISTDA | `gistda` | พื้นที่น้ำท่วมจากดาวเทียม รายตำบล (ไร่) + GeoJSON เต็ม | 1 วัน | `GISTDA_API_KEY` |
| ปภ. (disaster.go.th) | `disaster` | รายงานสถานการณ์: จำนวนจังหวัด/อำเภอ/ตำบล/หมู่บ้าน/ครัวเรือน/ผู้เสียชีวิต/บาดเจ็บ | 12 ชม. | – |
| สทนช. (onwr.go.th) | `onwr` | ประกาศเตือนภัย + จังหวัดเสี่ยง | 3 ชม. | – |
| สำนักการระบายน้ำ กทม. | `bma` | เซนเซอร์น้ำท่วมขังบนถนน 254 จุด (ซม.) จาก API ของ floodbangkok.bangkok.go.th | 15 นาที | – |
| กรมอุตุนิยมวิทยา | `tmd` | พยากรณ์ฝนรายชั่วโมง 48 ชม. (+ ภาพเรดาร์ ถ้าตั้ง `TMD_RADAR_URL`) | 3 ชม. | `TMD_API_TOKEN` (เฉพาะพยากรณ์) |

## ติดตั้ง

```bash
pip install -e ".[dev]"     # ต้องการ Python 3.10+ และ requests เท่านั้น
```

## การใช้งาน

```bash
thaiflood sources                       # ดูรายการแหล่ง
thaiflood collect                       # ดึงทุกแหล่ง 1 รอบ
thaiflood collect thaiwater bma         # ดึงเฉพาะบางแหล่ง
thaiflood serve                         # ติดตั้งในเครื่อง: ดึงตามรอบ + สร้าง dashboard + เปิดเว็บ (ดูด้านล่าง)
thaiflood schedule                      # รันค้างไว้ ดึงแต่ละแหล่งตามรอบในตารางด้านบน (ไม่สร้างหน้าเว็บ)
thaiflood latest --hours 24             # สรุปสถานการณ์: สถานีวิกฤต, ฝนหนัก ≥35 มม., พื้นที่ท่วม, จุดท่วมขัง กทม., ประกาศล่าสุด
thaiflood latest --province เชียงราย
thaiflood stats                         # มีข้อมูลอะไรบ้าง ช่วงเวลาไหน
thaiflood export out.csv --kind waterlevel --province เชียงใหม่ --since 2024-09-01
thaiflood reports --source disaster     # รายงาน/ประกาศ (JSON lines)
```

(ไม่ได้ติดตั้งก็ใช้ `python -m thaiflood ...` ได้)

### Interactive Dashboard (HTML ไฟล์เดียว)

```bash
thaiflood dashboard                         # -> thaiflood_YYYYMMDD_HHMM.html (ข้อมูลย้อนหลัง 7 วัน)
thaiflood dashboard flood.html --days 30    # ฝังข้อมูล 30 วัน
thaiflood dashboard --province เชียงราย     # เฉพาะจังหวัด (ไฟล์เล็กลง)
thaiflood dashboard --collect               # ดึงข้อมูลใหม่ก่อนแล้วค่อยสร้าง
```

ข้อมูลทั้งหมดฝังอยู่ในไฟล์ ดับเบิลคลิกเปิดในเบราว์เซอร์ หรือส่งต่อทางอีเมล/LINE ได้เลย ไม่ต้องมี server

- **ตัวกรอง:** จังหวัด, ช่วงเวลา (24 ชม. / 3 วัน / 7 วัน / ทั้งหมด), เปิด-ปิดชั้นข้อมูลบนแผนที่
- **ตัวเลขสรุป:** สถานีระดับน้ำวิกฤต, ฝนสูงสุด, พื้นที่ท่วมจากดาวเทียม, จุดท่วมขัง กทม., ผลกระทบตามรายงาน ปภ. ล่าสุด
- **แผนที่:** สีตามสถานะ (มีไอคอนและข้อความกำกับ ไม่ได้ใช้สีอย่างเดียว), ฝนแบ่งตามเกณฑ์กรมอุตุฯ, polygon พื้นที่ท่วมจาก GISTDA
- **กราฟย้อนหลัง:** คลิกสถานีบนแผนที่หรือในตาราง จะได้กราฟพร้อมเส้นตลิ่ง/ความจุเขื่อน ชี้ดูค่ารายจุดได้
- **ตาราง** ค้นหาและเรียงได้ทุกชนิดข้อมูล, แท็บรายงาน/ประกาศ, กราฟพยากรณ์ฝน 48 ชม. รายจุด
- ธีมสว่าง/มืด และรองรับมือถือ

แผนที่พื้นหลังกับไลบรารี Leaflet โหลดจากอินเทอร์เน็ต ถ้าออฟไลน์ แผนที่จะไม่ขึ้น แต่ตัวเลขสรุป กราฟ ตาราง และรายงานยังใช้งานได้

### ติดตั้งในเครื่อง / server ในออฟฟิศ (`thaiflood serve`)

คำสั่งเดียว: ดึงข้อมูลตามรอบของแต่ละแหล่ง → สร้าง dashboard ใหม่ → เปิดหน้าเว็บให้คนใน LAN เข้าดู
เหมาะกับเครื่องที่อยู่ในไทย (ดึงข้อมูล ปภ. / สทนช. / กทม. ที่บล็อกการเข้าจากต่างประเทศได้)

1. ติดตั้ง Python 3.10+ (Windows: ติ๊ก "Add python.exe to PATH" ตอนติดตั้ง)
2. ดาวน์โหลดโค้ดแล้วติดตั้ง
   ```bash
   git clone https://github.com/maximus77mx/max1.git
   cd max1
   pip install .
   ```
3. คัดลอก `.env.example` เป็น `.env` แล้วใส่ key (`GISTDA_API_KEY`, `SPHERE_API_KEY`, `TMD_API_TOKEN`)
   — key ของ sphere ที่จำกัด Clients ไว้ที่ github.io จะใช้ในเครื่องไม่ได้ ให้สร้าง key แยกที่ Clients เป็น IP/ชื่อเครื่อง
4. รัน
   ```bash
   thaiflood serve                  # http://localhost:8000
   thaiflood serve --port 8080      # เปลี่ยนพอร์ต
   thaiflood serve --host 127.0.0.1 # ให้เปิดได้เฉพาะเครื่องนี้
   ```
   หน้าจอจะบอกลิงก์สำหรับเครื่องอื่นใน LAN เช่น `http://192.168.1.20:8000/` (ครั้งแรกอาจต้องอนุญาตใน Firewall)

ข้อมูลอยู่ในโฟลเดอร์ `data/` (ฐานข้อมูล, ไฟล์ดิบ, หน้าเว็บที่ `data/site/`) — สำรองโฟลเดอร์นี้โฟลเดอร์เดียวพอ

**ให้รันเองเมื่อเปิดเครื่อง**
- Windows: Task Scheduler → Create Task → Trigger "At startup" → Action: Program `thaiflood`, Arguments `serve`,
  Start in = โฟลเดอร์ `max1` (ที่มีไฟล์ `.env`)
- Linux (systemd): สร้าง `/etc/systemd/system/thaiflood.service`
  ```ini
  [Unit]
  Description=Thai flood dashboard
  After=network-online.target

  [Service]
  WorkingDirectory=/opt/max1
  ExecStart=/usr/local/bin/thaiflood serve
  Restart=always

  [Install]
  WantedBy=multi-user.target
  ```
  แล้ว `sudo systemctl enable --now thaiflood`

### ติดตั้งบน Windows Server + IIS (หรือ Apache / Nginx)

หน้า dashboard เป็นไฟล์ static ล้วน (`index.html` + โฟลเดอร์ `geo/`) web server ใดก็เสิร์ฟได้ ไม่ต้องตั้ง Python/FastCGI ใน IIS
ส่วน Python ใช้แค่ "ดึงข้อมูลแล้วเขียนไฟล์" ผ่าน Task Scheduler

```
Task Scheduler (ทุก 10–15 นาที) → thaiflood-update.bat → C:\inetpub\wwwroot\flood\index.html + geo\ → IIS → ผู้ใช้
```

1. ติดตั้ง Python 3.10+ แล้ว
   ```bat
   git clone https://github.com/maximus77mx/max1.git C:\thaiflood\max1
   cd C:\thaiflood\max1
   python -m venv .venv
   .venv\Scripts\pip install .
   copy .env.example .env   &  REM แล้วใส่ key
   ```
   ถ้าออกอินเทอร์เน็ตผ่าน proxy ขององค์กร ใส่ `HTTPS_PROXY=http://proxy:port` ใน `.env` ด้วย
2. IIS: สร้าง Site/Application ชี้ไปที่ `C:\inetpub\wwwroot\flood` แล้วคัดลอก `deploy\iis\web.config` ไปวางในโฟลเดอร์นั้น
   (ตั้ง MIME `.json`, ปิด cache ของ `index.html`, เปิดการบีบอัด — ติดตั้ง role "Static Content Compression" ด้วยจะเร็วขึ้นมาก)
3. แก้ `APP_DIR` / `WEB_DIR` ใน `deploy\windows\thaiflood-update.bat` แล้วตั้ง Task Scheduler:
   Trigger ทุก 10–15 นาที, "Run whether user is logged on or not", บัญชีที่รันต้องมีสิทธิ์เขียนโฟลเดอร์เว็บ
4. รัน `thaiflood-update.bat` ครั้งแรกด้วยมือ แล้วเปิด `http://<server>/flood/` — log อยู่ที่ `data\update.log`

Apache/Nginx ใช้แนวเดียวกัน: ชี้ DocumentRoot/root ไปที่โฟลเดอร์ output แล้วใช้ cron แทน Task Scheduler
(`thaiflood collect --respect-intervals && thaiflood dashboard /var/www/flood/index.html`)

### ขึ้นออนไลน์ให้ทีมใช้ (GitHub Actions + GitHub Pages)

`.github/workflows/flood-dashboard.yml` ทำงานทุกชั่วโมง: ดึงข้อมูล → ลบข้อมูลที่เก่ากว่า 60 วัน → สร้าง dashboard → ขึ้น Pages
ฐานข้อมูลประวัติถูกส่งต่อระหว่างรอบด้วย Actions cache ส่วนหน้าเว็บจะโหลดใหม่เองทุก 15 นาที

ตั้งค่าครั้งเดียว:
1. **Settings → Secrets and variables → Actions** → เพิ่ม `GISTDA_API_KEY` (และ `TMD_API_TOKEN` ถ้ามี)
2. **Settings → Pages → Source:** เลือก **GitHub Actions**
3. merge branch นี้เข้า `master` (schedule ทำงานเฉพาะบน default branch)
4. **Actions → Flood dashboard → Run workflow** เพื่อรันรอบแรก

จากนั้นแชร์ลิงก์ `https://maximus77mx.github.io/max1/` ให้ทีม

#### ถ้า GitHub ไม่รันตามเวลา (ใช้ตัวตั้งเวลาภายนอก)

GitHub ไม่รับประกันเวลาของ `schedule` บาง repo ไม่ถูกรันเลย ใช้บริการภายนอก (เช่น cron-job.org) สั่งรันทุกชั่วโมงแทน:
1. สร้าง fine-grained token: GitHub → Settings → Developer settings → Fine-grained tokens → เลือกเฉพาะ repo นี้ → Permissions: **Actions: Read and write**
2. ตั้งงานรายชั่วโมงให้ส่ง `POST https://api.github.com/repos/<owner>/<repo>/actions/workflows/flood-dashboard.yml/dispatches`
   - Headers: `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`
   - Body: `{"ref":"master","inputs":{"respect_intervals":"true"}}` (ดึงเฉพาะแหล่งที่ถึงรอบ)

หมายเหตุ: GitHub Pages ของ repo public เปิดดูได้ทุกคนที่มีลิงก์ (key ไม่หลุด เพราะอยู่ใน Secret)
ถ้าต้องจำกัดเฉพาะทีม ใช้ Cloudflare Pages + Cloudflare Access หรือเซิร์ฟเวอร์ภายในที่รัน `thaiflood dashboard` ด้วย cron แทน
และ runner ของ GitHub อยู่ต่างประเทศ ถ้าเว็บหน่วยงานไหนบล็อก IP ต่างประเทศ แหล่งนั้นจะดึงไม่ได้ (ดู log ในแท็บ Actions)

### แผนที่ GISTDA sphere (ภาษาไทย) และชั้นน้ำท่วม

ตั้ง `SPHERE_API_KEY` แล้ว dashboard จะใช้แผนที่จาก GISTDA sphere เป็นค่าเริ่มต้น (แผนที่ถนน / ภาพดาวเทียมไทย / ภาพดาวเทียม + ถนน)
สลับได้จากปุ่มมุมขวาบนของแผนที่ ถ้าโหลด tile ไม่ได้ ระบบจะสลับไปใช้แผนที่สำรอง (CARTO) ให้เอง

- รูปแบบ URL ของ tile ตั้งได้ที่ `SPHERE_TILE_URL` (ใช้ `{layer}`, `{ext}`, `{key}`, `{z}/{x}/{y}`)
- ชั้นน้ำท่วมแบบ WMS: ตั้ง `SPHERE_FLOOD_WMS_URL` และ `SPHERE_FLOOD_WMS_LAYERS` ตามเอกสารของ sphere/GISTDA
- **key นี้จะอยู่ในหน้าเว็บ** (เบราว์เซอร์เป็นผู้โหลดแผนที่) ควรจำกัดโดเมนที่ใช้ key ได้ในหน้าจัดการ key ของ sphere
- บน GitHub Actions: เก็บ `SPHERE_API_KEY` เป็น Secret และ `SPHERE_FLOOD_WMS_URL` / `SPHERE_FLOOD_WMS_LAYERS` เป็น Variables
  ขั้น "Check sphere basemap" ใน log จะบอกว่า URL ของแผนที่ตอบกลับอะไร

### แผนที่ระบายสีรายจังหวัด/ตำบล และตาราง Hotspot

`thaiflood dashboard` จะดาวน์โหลดขอบเขตจังหวัดและตำบลครั้งแรก (เก็บไว้ที่ `data/boundaries/`) แล้ว
- ผูกทุกสถานีเข้ากับตำบลด้วยพิกัด (พื้นที่ท่วมของ GISTDA ใช้รหัสตำบลที่มากับข้อมูล)
- ภาพรวมทั้งประเทศระบายสีรายจังหวัด คลิกจังหวัดหรือเลือกจากตัวกรอง จะเห็นรายตำบล
- เลือกค่าที่ใช้ระบายสีได้ 4 แบบ: พื้นที่ท่วม (ไร่), % พื้นที่ตำบลที่ท่วม, ฝนสูงสุด 24 ชม., จำนวนสถานีระดับน้ำวิกฤต/เฝ้าระวัง
- ชั้น **ฝน 24 ชม. (พื้นที่)**: ประมาณค่าฝนระหว่างสถานีด้วย IDW (รัศมี ~40 กม.) ระบายสีเป็นพื้นผิวคลุมพื้นที่ ตัดตามขอบเขตประเทศ/จังหวัด
  พื้นที่ที่ไกลจากสถานีเกินรัศมีจะเว้นว่าง (เห็นช่องว่างของการตรวจวัด) — จุดสถานีเปิดเพิ่มได้จากชั้น "ฝน 24 ชม. (จุดสถานี)"
- ช่อง **ค้นหาตำบล** (ทุกตำบลทั่วประเทศ) พิมพ์ชื่อตำบล/อำเภอ/จังหวัด เช่น "สุเทพ" หรือ "ต.หนองหาร สันทราย"
  เลือกแล้วแผนที่ซูมไปที่ตำบล และแผงขวาแสดงสรุปตำบล: พื้นที่ท่วม, % ของตำบล, ฝน (ถ้าไม่มีสถานีในตำบลจะแสดงค่าประมาณการจากสถานีรอบข้าง),
  สถานีในตำบล และสถานีใกล้เคียงไม่เกิน 25 กม.
- แท็บ **Hotspot รายตำบล** จัดอันดับตำบลตามค่าที่เลือก คลิกแถวเพื่อซูมไปที่ตำบลนั้น

ขอบเขตตำบลถูกย่อรูปแล้วแยกไฟล์รายจังหวัดไว้ที่ `geo/` ข้างไฟล์ html (โหลดเฉพาะจังหวัดที่ดู)
จึงต้องเปิดผ่านเว็บ (เช่น GitHub Pages) ถ้าเปิดไฟล์จากเครื่องโดยตรง จะเห็นรายจังหวัดและตาราง Hotspot แต่ไม่เห็นขอบเขตตำบล

ค่าเริ่มต้นใช้ชุดข้อมูลเปิดจาก [chingchai/OpenGISData-Thailand](https://github.com/chingchai/OpenGISData-Thailand)
(ต้นทางไม่ได้ระบุสัญญาอนุญาต) เปลี่ยนเป็นแหล่งอื่นได้ที่ `TAMBON_GEOJSON_URL` / `PROVINCE_GEOJSON_URL`
โดยไฟล์ต้องมี property `tam_code`, `tam_th`, `amp_th`, `pro_code`, `pro_th`, `area_sqkm` (ตำบล) และ `pro_code`, `pro_th` (จังหวัด)
ไม่ต้องการส่วนนี้ใช้ `--no-geo`

### ข้อมูลย้อนหลัง (Historical)

1. **สะสมเอง** — ให้ `thaiflood schedule` รันต่อเนื่อง (systemd/Docker/cron) ข้อมูลทุกรอบจะถูก upsert
   ด้วย key `(source, kind, station_id, observed_at)` จึงรันซ้ำได้โดยไม่เกิดข้อมูลซ้ำ
2. **Backfill ระดับน้ำรายสถานีจาก ThaiWater**
   ```bash
   thaiflood backfill --station 101 --station 102 --start 2024-08-01 --end 2024-10-31 --chunk-days 30
   ```
   (หา station id ได้จากคอลัมน์ `station_id` หลัง `collect thaiwater`)
3. **GISTDA** มีช่วง `1day / 3days / 7days / 30days` — `GistdaSource(...).collect(period="30days")`
4. **รายงาน PDF ของ ปภ.** ที่แกะอัตโนมัติไม่ได้ ให้กรอกตัวเลขเป็น JSON แล้ว
   `thaiflood import-report report.json` (ฟิลด์ตาม `Report` ใน `thaiflood/models.py`)

### รันเป็น cron แทน schedule

```cron
5 * * * *    cd /opt/thaiflood && thaiflood collect thaiwater
*/15 * * * * cd /opt/thaiflood && thaiflood collect bma
0 */3 * * *  cd /opt/thaiflood && thaiflood collect onwr tmd
0 */12 * * * cd /opt/thaiflood && thaiflood collect disaster
30 9 * * *   cd /opt/thaiflood && thaiflood collect gistda
```

## โครงสร้างข้อมูล

ข้อมูลอยู่ที่ `./data/` (เปลี่ยนได้ด้วย `--data-dir` หรือ `THAIFLOOD_DATA_DIR`)

- `data/thaiflood.sqlite3`
  - `observations` — ค่าตัวเลขรายจุด/เวลา: `source, kind, station_id, observed_at, value, unit, name, province, amphoe, tambon, lat, lon, status, extra(JSON)`
    - `kind`: `waterlevel` (m.MSL), `rain_24h` (mm), `dam_storage` (%), `flood_area` (ไร่), `street_flood` (cm), `rain_forecast` (mm/h)
  - `reports` — รายงาน/ประกาศ: `title, url, published_at, summary, provinces(JSON), metrics(JSON)`
  - `runs` — log ของการดึงแต่ละรอบ พร้อม error
- `data/raw/<source>/<YYYY-MM-DD>/<HHMMSS>_<name>` — payload ดิบทุกรอบ (GeoJSON ของ GISTDA ใช้ทำแผนที่ได้ทันที)

เวลาทั้งหมดเป็น ISO-8601 พร้อม timezone (ไม่ระบุ = เวลาไทย +07:00), ปี พ.ศ. แปลงเป็น ค.ศ. อัตโนมัติ

## ตั้งค่า (environment variables)

| ตัวแปร | ใช้ทำอะไร |
|---|---|
| `GISTDA_API_KEY` | key จาก https://api-gateway.gistda.or.th |
| `TMD_API_TOKEN` | token NWP API จาก https://data.tmd.go.th/nwpapi |
| `TMD_POINTS` | จุดพยากรณ์ `ชื่อ:lat:lon;...` |
| `THAIWATER_BASE`, `THAIWATER_*_PATH` | base URL / path ของ API ThaiWater |
| `GISTDA_BASE`, `DISASTER_URL`, `ONWR_URL`, `BMA_DDS_URL`, `TMD_NWP_BASE`, `TMD_RADAR_URL` | URL ของแต่ละแหล่ง |
| `THAIFLOOD_DATA_DIR`, `THAIFLOOD_TIMEOUT`, `THAIFLOOD_USER_AGENT` | ทั่วไป |

## ข้อควรรู้

- **endpoint ยังไม่ได้ทดสอบกับเซิร์ฟเวอร์จริง** — สภาพแวดล้อมที่พัฒนาถูกบล็อกไม่ให้ออกไปยังโดเมน `.go.th`/`.or.th`/`thaiwater.net`
  URL และชื่อฟิลด์อ้างอิงจากโครงสร้าง API สาธารณะที่ทราบ ตัว parser เขียนให้ทนต่อชื่อฟิลด์ที่ต่างกันเล็กน้อย
  และทุก URL แก้ได้ผ่าน env โดยไม่ต้องแก้โค้ด ควรรัน `thaiflood -v collect` ครั้งแรกแล้วตรวจ `data/raw/` ว่าได้ข้อมูลจริง
- กทม.: ใช้ API ที่หน้า floodbangkok.bangkok.go.th เรียกเอง (`items/sensor_profile` + `items/flood_notification`, ไม่ต้องใช้ key)
  จุดที่มีแจ้งเตือนภายใน `BMA_ACTIVE_MINUTES` (ค่าเริ่มต้น 60 นาที) ถือว่ายังท่วมตามค่าล่าสุด — เป็น API ไม่เป็นทางการ อาจเปลี่ยนได้;
  ตั้ง `BMA_API_BASE=` (ค่าว่าง) เพื่อกลับไปอ่านหน้าเว็บตาม `BMA_DDS_URL`
- ปภ. / สทนช. ไม่มี API สาธารณะ — อ่านจากหน้าเว็บ (คัดลิงก์ด้วยคำว่า อุทกภัย/น้ำท่วม/เตือนภัย ฯลฯ)
  ถ้าหน่วยงานปรับหน้าเว็บ ให้แก้ URL หรือปรับ `find_bulletin_links` / `parse_html_points`
- แหล่งหนึ่งล่มไม่กระทบแหล่งอื่น — error ถูกบันทึกในตาราง `runs` และแสดงตอน `collect`
- ใช้ข้อมูลตามเงื่อนไขของแต่ละหน่วยงาน และตั้งรอบดึงให้สุภาพ (ค่าเริ่มต้นไม่ถี่กว่าที่ต้นทางอัปเดต)

## โครงสร้างโค้ด

```
thaiflood/
  config.py        URL + รอบการดึง (override ด้วย env)
  models.py        Observation / Report / CollectResult
  storage.py       SQLite + raw files + export CSV
  collector.py     collect() และ run_schedule()
  cli.py           คำสั่ง thaiflood
  serve.py         thaiflood serve (ดึงตามรอบ + สร้างหน้าเว็บ + HTTP server)
  dashboard.py     สร้าง Interactive HTML (+ dashboard_template.html)
  geo.py           ขอบเขตจังหวัด/ตำบล, หาตำบลจากพิกัด, ย่อรูปทรง
  sources/         adapter ต่อแหล่ง: fetch แยกจาก parse เพื่อทดสอบด้วย fixture ได้
tests/             pytest + fixtures (ไม่ต้องต่อเน็ต)
```

เพิ่มแหล่งใหม่: สร้างคลาสสืบจาก `Source` ใน `thaiflood/sources/` ให้ `collect()` คืน `CollectResult`
แล้วลงทะเบียนใน `SOURCES` (`thaiflood/sources/__init__.py`) และ `DEFAULT_INTERVALS`
