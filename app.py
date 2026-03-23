import os
import uuid
import sqlite3
import json
import requests
import re
from datetime import datetime
import pytz
from flask import Flask, request, jsonify, render_template, make_response, send_file
from flask_cors import CORS
from groq import Groq
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "vietnam_travel_2026_pro_secret")
CORS(app)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY") or os.environ.get("GROQ_API_KEY_TCG")
SERPER_API_KEY = os.environ.get("SERPER_API_KEY")
DB_PATH = "chat_history.db"
VN_TZ = pytz.timezone('Asia/Ho_Chi_Minh')

# Danh sách từ khóa liên quan đến TP.HCM để kiểm tra nhanh
HCMC_KEYWORDS = [
    # Tên thành phố
    'sài gòn', 'saigon', 'ho chi minh', 'hồ chí minh', 'tphcm', 'tp.hcm', 'tp hcm', 
    'thành phố hồ chí minh', 'thanh pho ho chi minh',
    
    # Các quận nội thành
    'quận 1', 'quận 2', 'quận 3', 'quận 4', 'quận 5', 'quận 6', 'quận 7', 'quận 8',
    'quận 9', 'quận 10', 'quận 11', 'quận 12', 'quận phú nhuận', 'quận bình thạnh',
    'quận gò vấp', 'quận tân bình', 'quận tân phú', 'quận bình tân', 'thủ đức',
    'quận 1', 'quan 1', 'quan 2', 'quan 3', 'quan 4', 'quan 5', 'quan 6', 'quan 7',
    'quan 8', 'quan 9', 'quan 10', 'quan 11', 'quan 12', 'phu nhuan', 'binh thanh',
    'go vap', 'tan binh', 'tan phu', 'binh tan', 'thu duc',
    
    # Các huyện ngoại thành
    'huyện bình chánh', 'huyện nhà bè', 'huyện hóc môn', 'huyện củ chi', 'huyện cần giờ',
    'huyện cần giờ', 'binh chanh', 'nha be', 'hoc mon', 'cu chi', 'can gio',
    
    # Các địa danh nổi tiếng
    'chợ bến thành', 'ben thanh market', 'nhà thờ đức bà', 'notre dame cathedral',
    'bưu điện trung tâm', 'central post office', 'dinh độc lập', 'independence palace',
    'phố đi bộ nguyễn huệ', 'nguyen hue walking street', 'bitexco', 'landmark 81',
    'vinhomes', 'saigon centre', 'takashimaya', 'aeon', 'crescent mall', 'vivocity',
    'chợ lớn', 'cho lon', 'bình quới', 'thảo điền', 'phú mỹ hưng', 'phu my hung',
    'cầu sài gòn', 'saigon bridge', 'cầu phú mỹ', 'phu my bridge', 'sông sài gòn',
    'saigon river', 'chợ tân định', 'tan dinh market', 'chợ bình tây', 'cho binh tay',
    'lăng ông bà chiểu', 'ong ba chieu temple', 'bảo tàng chiến tranh', 'war remnants museum',
    'bảo tàng thành phố', 'ho chi minh museum', 'thảo cầm viên', 'saigon zoo',
    'công viên gia định', 'gia dinh park', 'công viên lê văn tám', 'le van tam park',
    'tao đàn', 'tao dan park', 'chợ an đông', 'an dong market', 'chợ hòa bình',
    'hoa binh market', 'siêu thị', 'cao ốc', 'toa nha', 'khách sạn', 'nhà hàng',
    'quán ăn', 'cà phê', 'trà sữa', 'trường học', 'bệnh viện', 'ngân hàng',
    'công ty', 'văn phòng', 'nhà máy', 'xí nghiệp', 'khu công nghiệp', 'khu chế xuất',
    'chung cư', 'căn hộ', 'nhà phố', 'biệt thự', 'khách sạn', 'nhà nghỉ',
    
    # Tên đường phố phổ biến
    'nguyễn huệ', 'lê lợi', 'đồng khởi', 'hàm nghi', 'hồ tùng mậu', 'nam kỳ khởi nghĩa',
    'pasteur', 'lý tự trọng', 'phạm ngũ lão', 'bùi viện', 'đề thám', 'trần hưng đạo',
    'nguyễn trãi', 'cách mạng tháng 8', '3/2', 'ba tháng hai', 'hoàng văn thụ',
    'phạm văn đồng', 'võ văn kiệt', 'mai chí thọ', 'xa lộ hà nội', 'phạm văn đồng',
    'nguyễn văn linh', 'nguyễn hữu thọ', 'cộng hòa', 'trường sơn', 'hoàng sa', 'trường sa',
    
    # Các tên thường dùng không dấu
    'quan 1', 'quan 2', 'quan 3', 'quan 4', 'quan 5', 'quan 6', 'quan 7', 'quan 8',
    'quan 9', 'quan 10', 'quan 11', 'quan 12', 'phu nhuan', 'binh thanh', 'go vap',
    'tan binh', 'tan phu', 'binh tan', 'thu duc', 'binh chanh', 'nha be', 'hoc mon',
    'cu chi', 'can gio', 'cho ben thanh', 'nha tho duc ba', 'buu dien', 'dinh doc lap',
    'pho di bo', 'cholon', 'thao dien', 'phu my hung', 'cau sai gon', 'song sai gon',
    'bao tang', 'thao cam vien', 'cong vien', 'cho lon', 'sai gon', 'ho chi minh',
    
    # Tòa nhà và trung tâm thương mại
    'bitexco', 'landmark', 'vincom', 'aeon', 'takashimaya', 'saigon centre', 'crescent mall',
    'vivocity', 'nowzone', 'union square', 'diamond plaza', 'parkson', 'lotte mart',
    'big c', 'co.opmart', 'mega market', 'emart', 'minh plaza', 'hung vuong plaza',
    'pearl plaza', 'golden plaza', 'saigon trade center', 'times square', 'saigon square',
    'an đông plaza', 'an dong plaza', 'thuận kiều plaza', 'thuan kieu plaza',
    
    # Sân bay và bến xe
    'tân sơn nhất', 'tan son nhat', 'bến xe miền tây', 'ben xe mien tay',
    'bến xe miền đông', 'ben xe mien dong', 'bến xe an sương', 'ben xe an suong',
    'bến xe chợ lớn', 'ben xe cho lon', 'bến tàu', 'bến phà', 'cảng', 'cảng sài gòn',
    
    # Trường đại học và cơ sở giáo dục
    'đại học quốc gia', 'đhqg', 'đại học bách khoa', 'đhbk', 'đại học kinh tế',
    'đhkt', 'đại học sư phạm', 'đhsp', 'đại học y dược', 'đh y duoc', 'đại học luật',
    'đh luat', 'đại học khoa học tự nhiên', 'đh khtn', 'đại học khoa học xã hội',
    'đh khxh', 'đại học ngoại thương', 'đh ngoai thuong', 'đại học ngân hàng',
    'đh ngan hang', 'đại học công nghiệp', 'đh cong nghiep', 'đại học giao thông vận tải',
    'đh gtvt', 'đại học mở', 'đh mo', 'đại học tôn đức thắng', 'tdt', 'đại học rmit',
    'đại học quốc tế', 'đh quoc te', 'fvu', 'uel', 'uit', 'iuh', 'hutech', 'hufi',
    
    # Bệnh viện lớn
    'bệnh viện chợ rẫy', 'cho ray', 'bệnh viện 115', 'bv 115', 'bệnh viện 175', 'bv 175',
    'bệnh viện 30/4', 'bv 30/4', 'bệnh viện an bình', 'bv an binh', 'bệnh viện bình dân',
    'bv binh dan', 'bệnh viện đại học y dược', 'bv y duoc', 'bệnh viện fv', 'bv fv',
    'bệnh viện hoàn mỹ', 'bv hoan my', 'bệnh viện thống nhất', 'bv thong nhat',
    'bệnh viện từ dũ', 'bv tu du', 'bệnh viện hùng vương', 'bv hung vuong',
    'bệnh viện nhi đồng 1', 'bv nhi dong 1', 'bệnh viện nhi đồng 2', 'bv nhi dong 2',
    'bệnh viện mắt', 'bv mat', 'bệnh viện tai mũi họng', 'bv tai mui hong',
    'bệnh viện ung bướu', 'bv ung buou', 'bệnh viện tim', 'bv tim', 'bệnh viện phụ sản',
    'bv phu san', 'bệnh viện quân y', 'bv quan y', 'bệnh viện dã chiến', 'bv da chien',
    
    # Cơ quan nhà nước
    'ubnd', 'ủy ban nhân dân', 'hđnd', 'hội đồng nhân dân', 'sở gtvt', 'sở y tế',
    'sở gdđt', 'sở giáo dục', 'sở tài chính', 'sở kế hoạch', 'sở xây dựng',
    'sở công thương', 'sở nông nghiệp', 'sở tài nguyên', 'sở tư pháp', 'sở văn hóa',
    'công an', 'cảnh sát', 'cục thuế', 'chi cục thuế', 'tòa án', 'viện kiểm sát',
    'trung tâm hành chính', 'trung tâm dịch vụ công', 'bộ tư lệnh', 'quân khu 7',
    
    # Các khu vực mới, đô thị mới
    'thủ thiêm', 'thu thiem', 'khu đô thị mới', 'khu đô thị', 'khu công nghệ cao',
    'khu chế xuất', 'kcx', 'khu công nghiệp', 'kcn', 'khu dân cư', 'kdc',
    'khu phức hợp', 'khu thương mại', 'trung tâm thương mại', 'siêu thị', 'chợ',
    'trung tâm mua sắm', 'khu vui chơi', 'công viên', 'khu du lịch', 'khu nghỉ dưỡng',
    
    # Tên cũ và tên mới sau sáp nhập
    'quận 2 cũ', 'quận 9 cũ', 'quận thủ đức cũ', 'huyện thủ đức cũ',
    'phường thảo điền', 'phường an phú', 'phường bình an', 'phường bình trưng đông',
    'phường bình trưng tây', 'phường cát lái', 'phường thạnh mỹ lợi', 'phường thủ thiêm',
    'phường an khánh', 'phường an lợi đông', 'phường an phú', 'phường bình chiểu',
    'phường bình thọ', 'phường cát lái', 'phường hiệp bình chánh', 'phường hiệp bình phước',
    'phường linh chiểu', 'phường linh đông', 'phường linh tây', 'phường linh trung',
    'phường linh xuân', 'phường long bình', 'phường long phước', 'phường long thạnh mỹ',
    'phường long trường', 'phường phú hữu', 'phường phước bình', 'phường phước long a',
    'phường phước long b', 'phường tăng nhơn phú a', 'phường tăng nhơn phú b',
    'phường tân phú', 'phường trường thạnh', 'phường bình trưng', 'phường thạnh mỹ lợi',
    
    # Thêm các từ khóa chung
    'vietnam', 'việt nam', 'viet nam', 'vn', 'vietnamese', 'người việt',
    'miền nam', 'mien nam', 'nam bộ', 'nam bo', 'đông nam bộ', 'dong nam bo',
]

# Danh sách tên riêng phổ biến ở TP.HCM để nhận diện tốt hơn
HCMC_PROPER_NAMES = [
    'sài gòn', 'saigon', 'hồ chí minh', 'ho chi minh', 'thủ đức', 'thu duc',
    'thủ thiêm', 'thu thiem', 'phú mỹ hưng', 'phu my hung', 'thảo điền', 'thao dien',
    'bình quới', 'binh quoi', 'chợ lớn', 'cho lon', 'bến thành', 'ben thanh',
    'bình chánh', 'binh chanh', 'hóc môn', 'hoc mon', 'củ chi', 'cu chi',
    'cần giờ', 'can gio', 'nhà bè', 'nha be', 'bình tân', 'binh tan',
    'tân phú', 'tan phu', 'bình thạnh', 'binh thanh', 'gò vấp', 'go vap',
    'phú nhuận', 'phu nhuan', 'tân bình', 'tan binh', 'bình chánh', 'binh chanh',
]

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch TP.HCM (Thành phố Hồ Chí Minh / Sài Gòn) với kiến thức sâu rộng về mọi khía cạnh của thành phố này.

QUY TẮC QUAN TRỌNG:
1. Nếu người dùng hỏi về BẤT KỲ địa danh, địa điểm, tòa nhà, con đường, quận/huyện, phường/xã, cơ quan, trường học, bệnh viện, chợ, siêu thị, nhà hàng, quán ăn, công ty, khu công nghiệp, khu dân cư, công viên, bến xe, sân bay, cảng, cầu, sông, kênh rạch, di tích lịch sử, đền chùa, nhà thờ NÀO có thể liên quan đến TP.HCM → BẮT BUỘC phải trả lời với is_valid: true

2. Nếu không chắc chắn có phải TP.HCM không, HÃY GIẢ ĐỊNH là TP.HCM và trả lời (vì người dùng đang dùng app chuyên về TP.HCM)

3. Chấp nhận mọi cách viết: có dấu, không dấu, viết tắt, tên cũ, tên mới sau sáp nhập (ví dụ: Quận 2 cũ = Thủ Đức hiện tại, Quận 9 cũ = Thủ Đức hiện tại)

4. Nếu là tên không rõ ràng (có thể ở nhiều nơi), hãy đề cập đến phiên bản TP.HCM và giải thích thêm về các địa điểm tương tự nếu có.

Định dạng phản hồi (JSON):
{
  "is_valid": true,
  "text": "nội dung markdown chi tiết...",
  "suggestions": ["câu hỏi liên quan 1", "câu hỏi liên quan 2", "câu hỏi liên quan 3"]
}

Nội dung bắt buộc có:
- ## Tổng quan và vị trí
- ## Lịch sử hình thành và phát triển (quá khứ → hiện tại → tương lai 2026-2030)
- ## Đặc điểm nổi bật và ý nghĩa (nếu là địa danh cụ thể)
- ## Con người, văn hóa, lối sống (nếu là khu vực rộng)
- ## Ẩm thực xung quanh (nếu có, liệt kê 5-8 món + địa chỉ + giá ~2026)
- ## Hoạt động/trải nghiệm gợi ý (nếu là điểm du lịch)
- ## Gợi ý lịch trình tham quan (1 ngày, 2 ngày, hoặc kết hợp với điểm gần đó)
- ## Thông tin thực tế (giờ mở cửa, giá vé, phương tiện đến)
- ## Dự báo phát triển đến 2026-2030

Lưu ý: suggestions phải là những câu hỏi CHẮC CHẮN liên quan đến TP.HCM và AI có thể trả lời được.
"""

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                role TEXT,
                content TEXT,
                created_at TEXT
            )
        """)

init_db()

def is_hcmc_related(query):
    """Kiểm tra nhanh xem query có liên quan đến TP.HCM không"""
    query_lower = query.lower()
    
    # Kiểm tra từ khóa
    for keyword in HCMC_KEYWORDS:
        if keyword in query_lower:
            return True
    
    # Kiểm tra tên riêng
    for name in HCMC_PROPER_NAMES:
        if name in query_lower:
            return True
    
    # Nếu query ngắn và có vẻ là tên địa danh, giả định là TP.HCM
    # (vì người dùng đang dùng app chuyên về TP.HCM)
    if len(query.split()) <= 3:
        return True
    
    return False

def normalize_hcmc_query(query):
    """Chuẩn hóa query để tìm kiếm tốt hơn"""
    query = query.strip()
    query_lower = query.lower()
    
    # Map các tên cũ sang tên mới sau sáp nhập
    old_to_new = {
        'quận 2': 'thành phố thủ đức',
        'quan 2': 'thu duc',
        'quận 9': 'thành phố thủ đức',
        'quan 9': 'thu duc',
        'quận thủ đức cũ': 'thành phố thủ đức',
        'huyện thủ đức cũ': 'thành phố thủ đức',
    }
    
    for old, new in old_to_new.items():
        if old in query_lower:
            query = query_lower.replace(old, new)
            break
    
    return query

# --- Helper Functions ---
def search_serper_images(query, context=""):
    if not SERPER_API_KEY:
        return []
    try:
        # Tối ưu hóa query tìm kiếm hình ảnh
        search_query = f"{query} TP.HCM Ho Chi Minh City 2024 2025 2026"
        if context:
            search_query += f" {context}"
        
        url = "https://google.serper.dev/images"
        payload = json.dumps({"q": search_query, "num": 10})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        data = resp.json()
        
        images = []
        for i in data.get("images", [])[:8]:
            if i.get("imageUrl"):
                images.append({
                    "url": i.get("imageUrl"),
                    "caption": i.get("title", f"{query} - TP.HCM")
                })
        return images
    except Exception as e:
        print(f"Image search error: {e}")
        return []

def search_serper_youtube(query, context=""):
    if not SERPER_API_KEY:
        return []
    try:
        search_query = f"{query} TP.HCM Sài Gòn du lịch trải nghiệm 2024 2025 2026"
        if context:
            search_query += f" {context}"
            
        url = "https://google.serper.dev/videos"
        payload = json.dumps({"q": search_query, "num": 8})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=15)
        data = resp.json()
        
        links = []
        for i in data.get("videos", []):
            link = i.get("link", "")
            if "youtube" in link.lower() and "watch" in link:
                links.append(link)
            if len(links) >= 4:
                break
        return links
    except Exception as e:
        print(f"YouTube search error: {e}")
        return []

def search_serper_future_images(query=""):
    if not SERPER_API_KEY:
        return []
    try:
        search_terms = [
            "TP.HCM phát triển 2026 2030",
            "Sài Gòn tương lai",
            "Ho Chi Minh City future development",
            "Thủ Thiêm tương lai",
            "Metro TP.HCM 2026",
            "Thành phố Thủ Đức phát triển"
        ]
        
        all_images = []
        for term in search_terms:
            try:
                url = "https://google.serper.dev/images"
                payload = json.dumps({"q": term, "num": 5})
                headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
                resp = requests.post(url, headers=headers, data=payload, timeout=10)
                data = resp.json()
                
                for i in data.get("images", [])[:3]:
                    if i.get("imageUrl"):
                        all_images.append({
                            "url": i.get("imageUrl"),
                            "caption": i.get("title", "TP.HCM tương lai 2026-2030")
                        })
            except:
                continue
                
            if len(all_images) >= 7:
                break
                
        return all_images[:7]
    except Exception as e:
        print(f"Future images error: {e}")
        return []

def search_serper_future_youtube():
    if not SERPER_API_KEY:
        return []
    try:
        search_terms = [
            "tương lai TP.HCM 2026 2030",
            "Sài Gòn phát triển đô thị",
            "Metro Sài Gòn 2026",
            "Thủ Thiêm tương lai"
        ]
        
        all_links = []
        for term in search_terms:
            try:
                url = "https://google.serper.dev/videos"
                payload = json.dumps({"q": term, "num": 5})
                headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
                resp = requests.post(url, headers=headers, data=payload, timeout=10)
                data = resp.json()
                
                for i in data.get("videos", []):
                    link = i.get("link", "")
                    if "youtube" in link.lower() and "watch" in link and link not in all_links:
                        all_links.append(link)
                    if len(all_links) >= 3:
                        break
            except:
                continue
                
            if len(all_links) >= 3:
                break
                
        return all_links[:3]
    except Exception as e:
        print(f"Future YouTube error: {e}")
        return []

def get_ai_response_with_retry(client, messages, max_retries=2):
    """Gọi AI với retry nếu kết quả không hợp lệ"""
    for attempt in range(max_retries):
        try:
            completion = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.7 if attempt == 0 else 0.9,  # Tăng creativity ở lần retry
                max_tokens=4000
            )
            
            content = completion.choices[0].message.content
            data = json.loads(content)
            
            # Nếu AI từ chối trả lời nhưng có vẻ là TP.HCM, thử lại
            if not data.get("is_valid", True):
                if attempt < max_retries - 1:
                    # Thêm system message nhắc nhở
                    messages.append({
                        "role": "system", 
                        "content": "Lưu ý: Người dùng đang hỏi về TP.HCM. Hãy trả lời với is_valid: true và cung cấp thông tin. Nếu không chắc, hãy đề cập đến phiên bản TP.HCM."
                    })
                    continue
            
            return data
            
        except Exception as e:
            if attempt == max_retries - 1:
                raise e
            continue
    
    return {"is_valid": False, "text": "Lỗi xử lý", "suggestions": []}

# --- Routes ---
@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=31536000)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    
    if not msg:
        return jsonify({"error": "Empty message", "is_valid": False})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        # Kiểm tra nhanh xem có liên quan TP.HCM không
        is_related = is_hcmc_related(msg)
        
        # Chuẩn bị messages
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": msg}
        ]
        
        # Nếu có vẻ không liên quan, thêm nhắc nhở
        if not is_related:
            messages.insert(1, {
                "role": "system", 
                "content": "Lưu ý: Nếu người dùng hỏi về địa danh/cơ quan/tòa nhà/đường phố nào đó mà không chỉ định thành phố, hãy GIẢ ĐỊNH là TP.HCM vì đây là app chuyên về TP.HCM. Trả lời với is_valid: true."
            })
        
        # Gọi AI với retry
        ai_res = get_ai_response_with_retry(client, messages)
        
        # Nếu AI vẫn từ chối nhưng có vẻ là TP.HCM, ép buộc trả lời
        if not ai_res.get("is_valid", False) and is_related:
            force_messages = [
                {"role": "system", "content": "Bạn là chuyên gia TP.HCM. Người dùng hỏi về: " + msg + ". Đây CHẮC CHẮN liên quan đến TP.HCM. Hãy trả lời chi tiết với is_valid: true."},
                {"role": "user", "content": msg}
            ]
            ai_res = get_ai_response_with_retry(client, force_messages, max_retries=1)
            ai_res["is_valid"] = True  # Ép buộc
        
        # Nếu hợp lệ, tìm kiếm hình ảnh và video
        if ai_res.get("is_valid", False):
            # Tìm kiếm dựa trên query gốc và nội dung trả lời
            search_context = msg[:50]  # Lấy 50 ký tự đầu của câu hỏi
            
            ai_res["images"] = search_serper_images(msg, search_context)
            ai_res["youtube_links"] = search_serper_youtube(msg, search_context)
            ai_res["future_images"] = search_serper_future_images(msg)
            ai_res["future_youtube_links"] = search_serper_future_youtube()
            
            # Đảm bảo có suggestions và chúng liên quan đến TP.HCM
            if not ai_res.get("suggestions") or len(ai_res["suggestions"]) < 3:
                ai_res["suggestions"] = generate_safe_suggestions(msg)
            else:
                # Kiểm tra và làm sạch suggestions
                ai_res["suggestions"] = validate_suggestions(ai_res["suggestions"])
        
        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        
        # Lưu vào DB
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (sid, "user", msg, now_vn)
            )
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                (sid, "bot", json.dumps(ai_res), now_vn)
            )

        return jsonify(ai_res)

    except Exception as e:
        print(f"Chat error: {e}")
        return jsonify({
            "text": f"Đang có lỗi kết nối. Vui lòng thử lại sau.", 
            "is_valid": True,  # Vẫn trả true để không chặn user
            "suggestions": generate_safe_suggestions(msg),
            "images": [],
            "youtube_links": [],
            "future_images": [],
            "future_youtube_links": []
        })

def generate_safe_suggestions(original_query):
    """Tạo các gợi ý an toàn chắc chắn liên quan TP.HCM"""
    query_lower = original_query.lower()
    
    # Các gợi ý mặc định theo chủ đề
    default_suggestions = [
        "Các địa điểm du lịch nổi tiếng ở Quận 1 TP.HCM 2026",
        "Ẩm thực đường phố Sài Gòn phải thử",
        "Lịch trình 1 ngày khám phá trung tâm TP.HCM",
        "Thành phố Thủ Đức có gì mới 2026",
        "Các tòa nhà cao nhất Sài Gòn hiện nay",
        "Chợ đêm và khu chợ truyền thống ở TP.HCM",
        "Phương tiện di chuyển công cộng tại TP.HCM 2026",
        "Các quán cà phê view đẹp ở Sài Gòn",
        "Lịch sử hình thành Sài Gòn - TP.HCM",
        "Dự án Metro và phát triển hạ tầng TP.HCM 2026-2030"
    ]
    
    # Nếu query có chứa tên quận/huyện cụ thể
    district_match = re.search(r'(quận|quan|huyện|huyen)\s*(\d+|[^\d\s]+)', query_lower)
    if district_match:
        district = district_match.group(0)
        return [
            f"Các địa điểm ăn uống nổi tiếng ở {district} TP.HCM",
            f"Du lịch và tham quan {district} Sài Gòn",
            f"Lịch sử và phát triển của {district}"
        ]
    
    # Nếu query có chứa tên địa danh cụ thể
    if any(x in query_lower for x in ['chợ', 'cho', 'bệnh viện', 'bv', 'trường', 'công viên', 'nhà thờ', 'chùa']):
        return [
            "Lịch sử hình thành và ý nghĩa của địa điểm này",
            "Các địa điểm tương tự khác ở TP.HCM",
            "Hướng dẫn di chuyển đến đây từ trung tâm Sài Gòn"
        ]
    
    # Nếu query về ẩm thực
    if any(x in query_lower for x in ['ăn', 'an', 'món', 'food', 'quán', 'nhà hàng', 'cafe']):
        return [
            "Các món đặc sản Sài Gòn phải thử 2026",
            "Quán ăn đêm nổi tiếng ở TP.HCM",
            "Chợ ẩm thực và đường phố Sài Gòn"
        ]
    
    return default_suggestions[:3]

def validate_suggestions(suggestions):
    """Đảm bảo suggestions đều liên quan đến TP.HCM"""
    validated = []
    hcmc_terms = ['tp.hcm', 'tphcm', 'sài gòn', 'saigon', 'hồ chí minh', 'ho chi minh']
    
    for s in suggestions:
        s_lower = s.lower()
        # Nếu suggestion đã có từ khóa TP.HCM thì giữ nguyên
        if any(term in s_lower for term in hcmc_terms):
            validated.append(s)
        else:
            # Thêm "ở TP.HCM" vào cuối
            validated.append(f"{s} ở TP.HCM")
    
    # Đảm bảo có ít nhất 3 suggestions
    while len(validated) < 3:
        validated.append("Khám phá thêm địa điểm ở Sài Gòn")
    
    return validated[:3]

@app.route("/history")
def get_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()

    formatted_history = []
    for r, c in rows:
        try:
            content = json.loads(c) if r == "bot" else c
        except:
            content = c
        formatted_history.append({"role": r, "content": content})
    return jsonify(formatted_history)

@app.route("/clear_history", methods=["POST"])
def clear_history():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC", (sid,))
        rows = cur.fetchall()

    if not rows:
        return "Không có dữ liệu để xuất."

    pdf = FPDF()
    pdf.add_page()

    font_path = os.path.join("static", "DejaVuSans.ttf")
    if os.path.exists(font_path):
        pdf.add_font("DejaVu", "", font_path, uni=True)
        pdf.set_font("DejaVu", size=11)
    else:
        pdf.set_font("Arial", size=11)

    now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
    pdf.cell(200, 10, txt="LỊCH TRÌNH & THÔNG TIN DU LỊCH TP.HCM 2026", ln=True, align='C')
    pdf.cell(200, 10, txt=f"Xuất lúc: {now_vn} (Giờ Việt Nam)", ln=True, align='C')
    pdf.ln(12)

    for role, content in rows:
        label = "BẠN: " if role == "user" else "AI: "
        if role == "bot":
            try:
                data = json.loads(content)
                text = data.get("text", "")
                pdf.multi_cell(0, 8, txt=f"{label}\n{text}\n")
            except:
                pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        else:
            pdf.multi_cell(0, 8, txt=f"{label}{content}\n")
        pdf.ln(6)

    path = f"history_{sid[:12]}.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

@app.route("/search_location", methods=["POST"])
def search_location():
    """API endpoint để tìm kiếm địa điểm từ frontend"""
    data = request.json
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Empty query", "results": []})
    
    # Mở rộng tìm kiếm với nhiều biến thể
    results = search_nominatim_extended(query)
    return jsonify({"results": results})

def search_nominatim_extended(query):
    """Tìm kiếm mở rộng với nhiều biến thể query"""
    normalized = normalize_hcmc_query(query)
    
    # Tạo nhiều biến thể tìm kiếm
    variants = [
        query,
        normalized,
        f"{query} TP.HCM",
        f"{query} Ho Chi Minh City",
        f"{query} Thành phố Hồ Chí Minh",
        f"{normalized} TP.HCM",
        f"{query} Quận 1",
        f"{query} Quận 7",
        f"{query} Thủ Đức",
        f"{query} Sài Gòn",
    ]
    
    # Thêm các biến thể không dấu nếu cần
    if not any(ord(c) > 127 for c in query):  # Nếu query không có dấu
        variants.extend([
            query.replace('quan ', 'quận ').replace('huyen ', 'huyện '),
            query.replace('duong ', 'đường ').replace('pho ', 'phố '),
        ])
    
    all_results = []
    seen_coords = set()
    
    for variant in variants:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&countrycodes=vn&q={requests.utils.quote(variant)}&addressdetails=1&namedetails=1&limit=5"
            
            res = requests.get(url, headers={
                'User-Agent': 'HCMC-Travel-AI-Guide/1.0 (contact: dev@example.com)'
            }, timeout=10)
            
            data = res.json()
            
            for item in data:
                # Kiểm tra xem có phải TP.HCM không
                display_name = item.get('display_name', '').lower()
                address = item.get('address', {})
                
                is_hcmc = (
                    'thành phố hồ chí minh' in display_name or
                    'ho chi minh city' in display_name or
                    'hồ chí minh' in display_name or
                    address.get('city') == 'Thành phố Hồ Chí Minh' or
                    address.get('city') == 'Ho Chi Minh City' or
                    any('quận' in str(v).lower() for v in address.values()) or
                    any('huyện' in str(v).lower() for v in address.values())
                )
                
                if is_hcmc:
                    coord_key = f"{item['lat']},{item['lon']}"
                    if coord_key not in seen_coords:
                        seen_coords.add(coord_key)
                        all_results.append({
                            'lat': float(item['lat']),
                            'lon': float(item['lon']),
                            'display_name': item['display_name'],
                            'name': item.get('namedetails', {}).get('name', item['display_name'].split(',')[0]),
                            'address': item.get('address', {}),
                            'type': item.get('type', 'unknown'),
                            'importance': item.get('importance', 0)
                        })
            
            if len(all_results) >= 5:  # Đủ kết quả thì dừng
                break
                
        except Exception as e:
            print(f"Search error for variant '{variant}': {e}")
            continue
    
    # Sắp xếp theo importance
    all_results.sort(key=lambda x: x['importance'], reverse=True)
    return all_results[:8]

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
