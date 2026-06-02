import os
import sys
import re
import json
import time
import concurrent.futures
import pandas as pd
from datetime import datetime, timedelta
import pytz
import io

# Google 相關套件
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# 匯入 openai 庫以使用 Poe API
import openai

# ==========================================
# 🔐 0. 授權 Google API (Sheets & Drive)
# ==========================================
print("🔐 正在使用服務帳戶自動授權 Google API...")
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
# ⚠️ 請確保 service_account.json 已加入 .gitignore，切勿上傳至 GitHub
SERVICE_ACCOUNT_FILE = 'service_account.json'

try:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    print("✅ 服務帳戶授權成功！")
except Exception as e:
    print(f"❌ 授權失敗，請檢查 {SERVICE_ACCOUNT_FILE} 是否存在。錯誤訊息: {e}")
    sys.exit()

# ==========================================
# ⚙️ 1. 參數與配置設定 (⚠️ 請填寫你的網址與 ID)
# ==========================================
# 1. n8n raw data 的 Google Drive 資料夾 ID
N8N_RAW_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID"

# 2. 配置檔 Google Sheets 網址
KEYWORDS_SHEET_URL = "https://docs.google.com/"
GROUPINFO_SHEET_URL = "https://docs.google.com/"

# 3. 大統一 Google Sheet 的網址與工作表名稱
MASTER_SHEET_URL = "https://docs.google.com/"
MASTER_WORKSHEET_NAME = "Sheet1" 

# 4. 目標聊天記錄日期設定 (留空自動抓昨天)
MANUAL_TARGET_DATE = ""

# 🔑 Poe API 設定
# ⚠️ 建議透過環境變數傳入，切勿將真實 API Key 寫死在程式碼中
POE_API_KEY = os.environ.get("POE_API_KEY", "YOUR_POE_API_KEY_HERE")
POE_MODEL = "gemini-2.5-flash" 

poe_client = openai.OpenAI(
    api_key=POE_API_KEY,
    base_url="https://api.poe.com/v1",
)

# ⚠️ 已脫敏：替換為假資料。請在本地端或環境變數中設定真實的手機號碼清單
SEEDER_PHONES = {"12345678", "87654321", "11223344", "55667788"}

STANDARD_BRANDS = [
    "雅培心美力", "Apta Platinum", "Apta Essensis", "Apta Neo", "牛欄牌", 
    "美素", "美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature", 
    "Hipp", "Illuma", "Illuma 有機", "美贊臣 A+", "美贊臣 Enfinitas", 
    "雀巢能恩", "雀巢全護"
]

FINAL_HEADERS = [
    "Group", "GroupID", "Date", "Time", "userPhone", "Internal", 
    "quotedMessage", "messageBody", "brand", "keywords", "warning", "reply"
] + STANDARD_BRANDS

stats = {
    "csv_files": 0,
    "total_raw_rows": 0,
    "total_deduped_rows": 0,
    "need_ai_processing": 0,
    "ai_actually_processed": 0,
    "spam_detected": 0
}

def print_stage_dashboard(stage_name, metrics):
    print("\n" + "="*50)
    print(f"📊 {stage_name} - 統計看板")
    print("="*50)
    for key, value in metrics.items():
        print(f"{key:<22} : {value}")
    print("="*50 + "\n")

# ==========================================
# 🤖 2. AI 情感與垃圾分析函數
# ==========================================
def call_llm_analysis(body_text, quoted_text="", hit_kws_list=[], max_retries=3):
    marked_body = body_text
    marked_quoted = quoted_text
    
    sorted_kws = sorted(hit_kws_list, key=len, reverse=True)
    for kw in sorted_kws:
        if kw:
            pattern = re.compile(rf"(?<!【){re.escape(kw)}(?!】)")
            marked_body = pattern.sub(f"【{kw}】", marked_body)
            if marked_quoted:
                marked_quoted = pattern.sub(f"【{kw}】", marked_quoted)

    prompt = f"""# Role
    你是一位具備 15 年育兒經驗的香港母親，同時擔任頂級母嬰品牌公關與客服風控專家。你精通香港/廣東話的母嬰社群俚語。
    
    # Task
    解構輸入的社群留言（引言+回覆），執行「無效數據過濾 (isSpam)」與「品牌立場分析 (brand_analysis)」，最後嚴格輸出純 JSON 格式。
    ⚠️ 只能針對被【 】包覆的品牌關鍵詞進行分析。
    
    # 📚 Brand Mapping
    | 標準品牌名稱 | 對應的關鍵詞 (必定出現在【 】中) |
    | :--- | :--- |
    | 雅培心美力 | 雅培, 心美力, 保兒 |
    | Apta Platinum | Apta, Platinum, 白金 |
    | Apta Essensis | Essensis, HMO |
    | Apta Neo | Neo, 至熠, 新出奶粉, 離乳寶寶, 乳黃金球, 母乳脂球, 至熠3D乳黃金球, 乳脂 |
    | 牛欄牌 | 牛欄, 樂兒 |
    | 美素 | 美素, Friso, 佳兒 |
    | 美素金裝 | 金裝, Gold |
    | 美素皇家 | PRESTIGE, 皇家 |
    | 美素有機 | 有機, 自家農場 (當與美素/皇家一起討論時) |
    | 美素Kids | Kids |
    | 美素Signature | SIGNATURE, IGG, 免疫球蛋白, 免疫蛋白, 法拉 |
    | Hipp | 喜寶, Hipp, 德國 |
    | Illuma | Illuma, 藍罐 |
    | Illuma 有機 | 綠罐, 有機, Organic (當與 Illuma 一起討論時) |
    | 美贊臣 A+ | 美贊臣, A+ |
    | 美贊臣 Enfinitas | Enfinitas, 藍臻 |
    | 雀巢能恩 | 雀巢, 能恩 |
    | 雀巢全護 | 全護, Infini |
    
    # Negative Constraints & Rules
    1. 意圖解構 (isSpam): 純交易/抽獎/無關閒聊為 true。有評價、轉奶原因、詢問為 false。
    2. 情緒分析 (brand_analysis): 
       - "N" (負面/需客服介入): 生理不適、抱怨、焦慮疑問。
       - "P" (正面): 滿意、推介、穩定飲用 (如「無事」、「安心」)。
       - "I" (中立): 純詢價、客觀陳述。
    
    # Output Format
    強制輸出純 JSON 字串，以 `{{` 開頭，`}}` 結尾。
    {{
      "reasoning": "分析過程...",
      "isSpam": false,
      "brand_analysis": {{
        "標準品牌A": "N"
      }}
    }}
    
    # Input
    引言內容: {marked_quoted}
    回覆內容: {marked_body}
    """
    
    for attempt in range(max_retries):
        try:
            response = poe_client.responses.create(
                model=POE_MODEL,
                input=prompt
            )
            res_text = response.output_text.strip()
            
            # 清理 Markdown 標籤 (如 ```json ... ```)
            if res_text.startswith("```"):
                res_text = re.sub(r"^```[a-zA-Z]*\n", "", res_text)
                res_text = re.sub(r"\n```$", "", res_text)
                
            result = json.loads(res_text.strip())
            return True, result.get("isSpam", False), result.get("brand_analysis", {})
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2)
            else:
                print(f"⚠️ LLM 解析失敗: {e}")
                return False, False, {}

# ==========================================
# 📂 3. 透過 Google Drive API 下載目標日期的檔案
# ==========================================
hk_tz = pytz.timezone('Asia/Hong_Kong')
if MANUAL_TARGET_DATE:
    target_date_str = MANUAL_TARGET_DATE
else:
    target_date_str = (datetime.now(hk_tz) - timedelta(days=1)).strftime("%y%m%d")
print(f"📅 目標聊天記錄日期: [{target_date_str}]")

# 建立本地暫存資料夾
LOCAL_RAW_DIR = "./temp_raw_data"
os.makedirs(LOCAL_RAW_DIR, exist_ok=True)
daily_file_paths = []

print("🔄 正在透過 Google Drive API 搜尋並下載檔案...")
try:
    # 1. 搜尋包含目標日期的資料夾 (修正：加上減號避開生產日期)
    # 利用 000000 精準鎖定中間的聊天記錄日期，避開 Drive API 忽略符號的分詞特性
    query = f"'{N8N_RAW_FOLDER_ID}' in parents and name contains '{target_date_str}000000' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    results = drive_service.files().list(q=query, fields="files(id, name)").execute()
    folders = results.get('files', [])

    if not folders:
        print(f"⚠️ 找不到目標日期為 {target_date_str} 的資料夾。")
        sys.exit()

    for folder in folders:
        print(f"📂 找到資料夾: {folder['name']}")
        # 2. 搜尋資料夾內的 CSV/Excel 檔案
        file_query = f"'{folder['id']}' in parents and trashed = false"
        file_results = drive_service.files().list(q=file_query, fields="files(id, name)").execute()
        files = file_results.get('files', [])
        
        for file in files:
            if file['name'].endswith(('.xlsx', '.csv')) and not file['name'].startswith('~$'):
                print(f"   ⬇️ 下載檔案: {file['name']}")
                request = drive_service.files().get_media(fileId=file['id'])
                local_path = os.path.join(LOCAL_RAW_DIR, file['name'])
                fh = io.FileIO(local_path, 'wb')
                downloader = MediaIoBaseDownload(fh, request)
                done = False
                while done is False:
                    status, done = downloader.next_chunk()
                daily_file_paths.append(local_path)

except Exception as e:
    print(f"❌ 下載檔案失敗: {e}")
    sys.exit()

stats["csv_files"] = len(daily_file_paths)

# ---------------------------------------------------------
# 讀取 Google Sheets 配置檔 (Keywords & GroupInfo)
# ---------------------------------------------------------
print("🌐 正在從 Google Sheets 讀取配置檔 (Keywords & GroupInfo)...")
try:
    kw_sheet = gc.open_by_url(KEYWORDS_SHEET_URL).sheet1
    keywords_df = pd.DataFrame(kw_sheet.get_all_records())
    
    gi_sheet = gc.open_by_url(GROUPINFO_SHEET_URL).sheet1
    groupinfo_df = pd.DataFrame(gi_sheet.get_all_records())
    print("✅ 配置檔讀取成功！")
except Exception as e:
    print(f"❌ 讀取配置檔失敗: {e}")
    sys.exit()

group_map = {}
id_col = 'gus_id' if 'gus_id' in groupinfo_df.columns else ('GroupID' if 'GroupID' in groupinfo_df.columns else groupinfo_df.columns)
name_col = 'subject' if 'subject' in groupinfo_df.columns else ('GroupName' if 'GroupName' in groupinfo_df.columns else groupinfo_df.columns)

for _, row in groupinfo_df.iterrows():
    gid = str(row.get(id_col, '')).strip()
    if gid.endswith('.0'): gid = gid[:-2]
    gname = str(row.get(name_col, '')).strip()
    if gid and gid.lower() not in ['nan', 'none']:
        group_map[gid] = gname

brand_keywords = {}
exclude_keywords = []
all_brand_related_kws = set()

for _, row in keywords_df.iterrows():
    k_type = str(row.get('type', '')).strip()
    brand_name = str(row.get('brand', '')).strip()
    kw = str(row.get('keyword', '')).strip()
    
    if not kw: continue
    if k_type.lower() == 'exclude':
        exclude_keywords.append(kw)
    else:
        brand_keywords.setdefault(brand_name, []).append(kw)
        if brand_name and brand_name not in ["1", "nan", "None"]:
            all_brand_related_kws.add(kw)

print_stage_dashboard("環境與配置解析", {
    "📁 下載的目標檔案數": f"{stats['csv_files']} 個",
    "🏷️ 載入的品牌關鍵字數": f"{sum(len(v) for v in brand_keywords.values())} 個",
    "👥 載入的群組資訊數": f"{len(group_map)} 個"
})

# ==========================================
# ⚡ 4. 第一階段：規則匹配與打標
# ==========================================
def get_phone_score(phone):
    phone = str(phone).strip()
    if phone.startswith("852") and "@" not in phone: return 3  
    elif "@" not in phone and re.match(r'^\d+$', phone): return 2  
    else: return 1  

records_dict = {} 
print("⚡ 開始進行第一階段：規則匹配與打標...")
for file_path in daily_file_paths:
    file_name = os.path.basename(file_path)
    group_id = str(os.path.splitext(file_name)[0]).strip() 
    if group_id.endswith('.0'): group_id = group_id[:-2]
    group_name = group_map.get(group_id, "")

    try:
        day_df = pd.read_excel(file_path) if file_path.endswith('.xlsx') else pd.read_csv(file_path)
        day_df.columns = day_df.columns.str.strip()
        for col in ['Date2', 'Time', 'userPhone', 'messageBody', 'quotedMessage']:
            if col not in day_df.columns: day_df[col] = ""

        for _, row in day_df.iterrows():
            stats["total_raw_rows"] += 1
            body = str(row['messageBody']).strip()
            quoted_raw = row.get('quotedMessage')
            quoted = "" if pd.isna(quoted_raw) or str(quoted_raw).strip().lower() in ["nan", "null", "none"] else str(quoted_raw).strip()
            date_val = str(row['Date2']).strip()
            time_val = str(row['Time']).strip()
            phone_raw = str(row['userPhone']).strip()
            
            phone_for_check = re.sub(r'\D', '', phone_raw)
            if phone_for_check.startswith("852"): phone_for_check = phone_for_check[3:]
            if body.lower() == "image" or not body: continue

            internal_flag = "✓" if phone_for_check in SEEDER_PHONES else ""
            contains_exclude = any(ex_kw in body for ex_kw in exclude_keywords)

            hit_brands, hit_keywords = [], []
            brand_marks = {b: "" for b in STANDARD_BRANDS}
            has_brand_keyword = False
            
            if not contains_exclude:
                for brand, kws in brand_keywords.items():
                    brand_hit = False
                    for kw in kws:
                        if kw in body:
                            brand_hit = True
                            if kw not in hit_keywords: hit_keywords.append(kw)
                            if kw in all_brand_related_kws: has_brand_keyword = True
                    if brand_hit: hit_brands.append(brand)

            cleaned_body = re.sub(r'\s+', '', body)
            fingerprint = f"{group_id}_{date_val}_{time_val}_{cleaned_body}"
            
            brand_status = ""
            if hit_brands and has_brand_keyword:
                brand_status = "1"
                for b in hit_brands:
                    if b in STANDARD_BRANDS: brand_marks[b] = "✓"

            record = {
                "Group": group_name, "GroupID": group_id, "Date": date_val, "Time": time_val,
                "userPhone": phone_raw, "Internal": internal_flag, "quotedMessage": quoted,
                "messageBody": body, "brand": brand_status, "keywords": ", ".join(hit_keywords),
                "warning": "", "reply": "", **brand_marks
            }

            current_phone_score = get_phone_score(phone_raw)
            if fingerprint in records_dict:
                if current_phone_score > get_phone_score(records_dict[fingerprint]["userPhone"]):
                    records_dict[fingerprint] = record
            else:
                records_dict[fingerprint] = record
    except Exception as e:
        print(f"❌ 讀取檔案 {file_name} 失敗: {e}")

all_records = list(records_dict.values())
stats["total_deduped_rows"] = len(all_records)
stats["need_ai_processing"] = sum(1 for r in all_records if r["brand"] == "1")

# 新增：第一階段統計看板
print_stage_dashboard("第一階段：規則匹配與打標", {
    "💬 原始對話數據總行數": f"{stats['total_raw_rows']} 行",
    "📝 去重後保留的總行數": f"{stats['total_deduped_rows']} 行",
    "🎯 命中品牌需 AI 處理": f"{stats['need_ai_processing']} 行"
})

# ==========================================
# 🤖 5. 第二階段：精準 AI 分析
# ==========================================
print(f"🤖 開始進行第二階段：精準 AI 情感與垃圾分析...")
records_to_analyze = [r for r in all_records if r["brand"] == "1" and r["keywords"]]
total_to_analyze = len(records_to_analyze)
processed_count = 0

def process_single_record(record):
    kws_list = [k.strip() for k in record["keywords"].split(",") if k.strip()]
    success, is_spam, brand_analysis = call_llm_analysis(record["messageBody"], record["quotedMessage"], kws_list)
    return record, success, is_spam, brand_analysis

if total_to_analyze > 0:
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(process_single_record, record): record for record in records_to_analyze}
        for future in concurrent.futures.as_completed(futures):
            record = futures[future] 
            processed_count += 1
            try:
                _, success, is_spam, brand_analysis = future.result()
                if success:
                    stats["ai_actually_processed"] += 1
                    if is_spam:
                        stats["spam_detected"] += 1
                        record["brand"], record["keywords"] = "", ""
                        for b in STANDARD_BRANDS: record[b] = ""
                    else:
                        friso_sub_brands = ["美素金裝", "美素皇家", "美素有機", "美素Kids", "美素Signature"]
                        friso_sentiments = []

                        for std_brand, sentiment in brand_analysis.items():
                            if std_brand in STANDARD_BRANDS: 
                                record[std_brand] = sentiment
                                # 收集美素及子品牌的情緒
                                if std_brand in friso_sub_brands or std_brand == "美素":
                                    friso_sentiments.append(sentiment)
                        
                        # 處理美素母品牌同步邏輯 (優先級 N > P > I)
                        if friso_sentiments:
                            if "N" in friso_sentiments:
                                record["美素"] = "N"
                            elif "P" in friso_sentiments:
                                record["美素"] = "P"
                            elif "I" in friso_sentiments:
                                record["美素"] = "I"
            except Exception: pass

# ==========================================
# 💾 6. 數據清洗與寫入 Google Sheets
# ==========================================
print("💾 正在清洗數據並準備寫入 Google Sheets...")
final_df = pd.DataFrame(all_records)

if not final_df.empty:
    for col in FINAL_HEADERS:
        if col not in final_df.columns: final_df[col] = ""
    final_df = final_df[FINAL_HEADERS]
    final_df['Date_parsed'] = pd.to_datetime(final_df['Date'], errors='coerce', dayfirst=True)
    final_df['Date'] = final_df['Date_parsed'].dt.strftime('%Y-%m-%d')
    final_df = final_df.sort_values(by=['Date_parsed', 'GroupID', 'Time']).drop(columns=['Date_parsed']).fillna("")

    try:
        sh = gc.open_by_url(MASTER_SHEET_URL)
        worksheet = sh.worksheet(MASTER_WORKSHEET_NAME)
        worksheet.append_rows(final_df.values.tolist(), value_input_option='USER_ENTERED')
        print(f"✅ 成功將 {len(final_df)} 筆資料附加到 Google Sheet 中！")
    except Exception as e:
        print(f"❌ 寫入 Google Sheets 失敗: {e}")
else:
    print("⚠️ 目標日期無有效數據可寫入。")

print_stage_dashboard("最終階段：自動化任務完成", {
    "🎯 預期需 AI 處理數": f"{stats['need_ai_processing']} 行",
    "✅ AI 實際成功處理數": f"{stats['ai_actually_processed']} 行",
    "🗑️ 判定為 Spam (無效)": f"{stats['spam_detected']} 行",
    "📝 最終寫入 Sheets 行數": f"{len(final_df) if not final_df.empty else 0} 行"
})
