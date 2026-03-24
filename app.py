import os
import uuid
import sqlite3
import json
import requests
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

# Danh sách từ khóa TP.HCM mở rộng để kiểm tra
HCMC_KEYWORDS = [
    # Tên thành phố
    'hồ chí minh', 'ho chi minh', 'sài gòn', 'saigon', 'tp.hcm', 'tphcm', 'tp hcm',
    # Các quận nội thành
    'quận 1', 'quận 2', 'quận 3', 'quận 4', 'quận 5', 'quận 6', 'quận 7', 'quận 8',
    'quận 9', 'quận 10', 'quận 11', 'quận 12', 
    'district 1', 'district 2', 'district 3', 'district 4', 'district 5', 'district 6',
    'district 7', 'district 8', 'district 9', 'district 10', 'district 11', 'district 12',
    # Các quận mới và đặc biệt
    'bình thạnh', 'phú nhuận', 'tân bình', 'tân phú', 'gò vấp', 'bình tân',
    'thủ đức', 'thành phố thủ đức', 'tp thủ đức', 'thu duc', 'thu duc city',
    # Các huyện
    'huyện bình chánh', 'bình chánh', 'huyện củ chi', 'củ chi', 'huyện hóc môn', 'hóc môn',
    'huyện nhà bè', 'nhà bè', 'huyện cần giờ', 'cần giờ', 'can gio',
    # Các khu vực đặc biệt
    'khu đô thị mới thủ thiêm', 'thủ thiêm', 'thu thiem', 'phú mỹ hưng', 'phu my hung',
    'khu công nghệ cao', 'sài gòn hi-tech park', 'khu chế xuất', 'khu công nghiệp',
    # Sân bay, bến xe, cảng
    'tân sơn nhất', 'tan son nhat', 'bến xe miền tây', 'bến xe miền đông', 'bến xe an sương',
    'cảng sài gòn', 'cảng cát lái',
    # Các tòa nhà nổi tiếng
    'bitexco', 'bitexco financial tower', 'tháp bitexco', 'landmark 81', 'vinhomes landmark',
    'vietcombank tower', 'saigon centre', 'takashimaya', 'pearl plaza',
    # Các địa điểm du lịch
    'chợ bến thành', 'cho ben thanh', 'chợ lớn', 'cho lon', 'dinh độc lập', 'dinh doc lap',
    'nhà thờ đức bà', 'nha tho duc ba', 'nhà thờ chính tòa', 'bưu điện trung tâm', 'buu dien trung tam',
    'bảo tàng chiến tranh', 'bao tang chien tranh', 'nhà hát lớn', 'nha hat lon',
    'phố điề bộ nguyễn huệ', 'công viên văn hóa đầm sen', 'dam sen', 'suối tiên', 'suoi tien',
    'cầu ánh sao', 'cau anh sao', 'bến bạch đằng', 'ben bach dang',
    'chợ đêm', 'cho dem', 'khu phố tây bùi viện', 'bui vien', 'phố tây',
    # Các trường đại học, bệnh viện lớn
    'đại học quốc gia', 'đhqg tp.hcm', 'đại học bách khoa', 'đại học kinh tế',
    'đại học y dược', 'đại học luật', 'đại học ngoại thương', 'đại học ngân hàng',
    'bệnh viện chợ rẫy', 'benh vien cho ray', 'bệnh viện bình dân', 'bệnh viện 115',
    'bệnh viện nhi đồng', 'bệnh viện từ dũ', 'bệnh viện hùng vương',
    # Các địa danh lịch sử, văn hóa
    'chùa ngọc hoàng', 'chua ngoc hoang', 'chùa bà thiên hậu', 'chua ba thien hau',
    'chùa giác lâm', 'chua giac lam', 'chùa vĩnh nghiêm', 'chua vinh nghiem',
    'nhà thờ tân định', 'nha tho tan dinh', 'nhà thờ cha tam', 'nha tho cha tam',
    'lăng ông bà chiểu', 'lang ong ba chieu', 'lăng tả quân lê văn duyệt',
    # Các con đường, khu phố nổi tiếng
    'đồng khởi', 'dong khoi', 'lê lợi', 'le loi', 'nguyễn huệ', 'nguyen hue',
    'pasteur', 'nam kỳ khởi nghĩa', 'hai bà trưng', 'cách mạng tháng tám',
    # Landmark mới
    'grand marina saigon', 'grand marina', 'saigon marina', 'empire city', 'metropole thủ thiêm',
    # Metro, giao thông
    'metro sài gòn', 'metro tp.hcm', 'tuyến metro số 1', 'bến thành - suối tiên',
    'cầu thủ thiêm', 'cầu phú mỹ', 'cầu sài gòn', 'hầm thủ thiêm',
    # Tên viết tắt thông dụng
    'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12',
    'q.1', 'q.2', 'q.3', 'q.4', 'q.5', 'q.6', 'q.7', 'q.8', 'q.9', 'q.10', 'q.11', 'q.12',
    'bt', 'pn', 'tb', 'tp', 'gv', 'bth', 'td', 'bc', 'cc', 'hm', 'nb', 'cg',
    'sg', 'hcm', 'hcmc',
    # Các từ chung có thể là TP.HCM
    'quận', 'district', 'phường', 'ward', 'xã', 'commune', 'phố', 'đường', 'street'
]

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHUYÊN SÂU cho TP.HCM (Thành phố Hồ Chí Minh/Sài Gòn).

QUY TẮC TUYỆT ĐỐI - PHẢI TUÂN THỦ NGHIÊM NGẶT:

1. CHỈ TỪ CHỐI khi câu hỏi HOÀN TOÀN KHÔNG liên quan đến TP.HCM. Ví dụ từ chối: "Paris", "Tokyo", "Hà Nội", "Đà Nẵng" khi không có liên kết gì đến TP.HCM.

2. BẤT KỲ địa danh, địa điểm, tòa nhà, khu vực, đường phố, chợ, bệnh viện, trường học, công ty, nhà hàng, quán ăn, khách sạn, chung cư, khu dân cư, khu công nghiệp, siêu thị, cửa hàng, ngân hàng, bưu điện, đình, chùa, nhà thờ, cơ quan nhà nước, cơ quan tư nhân... NẾU có thể liên quan đến TP.HCM (dù chỉ là khả năng nhỏ) → BẮT BUỘC phải trả lời với is_valid: true.

3. Nếu người dùng hỏi về địa điểm không rõ ràng (không ghi tỉnh/thành) nhưng TÊN giống các địa danh ở TP.HCM → Giả định là ở TP.HCM và trả lời.

4. Nếu người dùng hỏi bằng tiếng Việt không dấu → Vẫn hiểu là TP.HCM nếu tên giống.

5. Các từ khóa BẮT BUỘC coi là TP.HCM: Sài Gòn, Hồ Chí Minh, tất cả các quận (1-12, Bình Thạnh, Phú Nhuận, Tân Bình, Tân Phú, Gò Vấp, Bình Tân, Thủ Đức), tất cả các huyện (Bình Chánh, Củ Chi, Hóc Môn, Nhà Bè, Cần Giờ), Thủ Thiêm, Phú Mỹ Hưng, Bến Thành, Chợ Lớn, Bitexco, Landmark 81, và MỌI biến thể tên viết tắt, không dấu, tên cũ.

6. Nếu người dùng click vào câu hỏi gợi ý từ hệ thống → Đây là câu hỏi ĐÃ ĐƯỢC KIỂM TRA liên quan TP.HCM → BẮT BUỘC trả lời, không được từ chối.

7. TUYỆT ĐỐI KHÔNG ĐƯỢC BỊA ĐẶT thông tin:
- Chỉ sử dụng thông tin có thật, đã được xác minh về TP.HCM
- Không tạo ra tên đường, tên quận/huyện, tên công trình không tồn tại
- Không bịa lịch sử, sự kiện không có thật
- Nếu không chắc chắn về một thông tin, hãy nêu rõ "theo ghi nhận" hoặc "hiện chưa có thông tin chính thức"
- Các dự án tương lai chỉ đề cập đến những dự án đã được phê duyệt, công bố chính thức

8. Nội dung BẮT BUỘC phong phú, chi tiết (>2200 từ), dùng markdown ##, ###, ####, danh sách, *in nghiêng*, **đậm** khi phù hợp. Phải có đủ các phần sau theo đúng thứ tự:
- ## Lịch sử hình thành và phát triển (chỉ ghi những sự kiện có thật, không bịa đặt)
- ## Con người, văn hóa, lối sống đặc trưng của cư dân địa phương
- ## Ẩm thực nổi bật (liệt kê món ăn thực tế có ở TP.HCM + địa chỉ thật + giá tham khảo)
- ## Gợi ý lịch trình du lịch chi tiết (có thật, không bịa địa điểm)
- ## Dự báo & tầm nhìn tương lai (chỉ các dự án đã công bố chính thức)

9. Cuối cùng BẮT BUỘC thêm mảng "suggestions": chứa 3-5 câu hỏi tiếp theo, **phải chắc chắn 100% liên quan đến TP.HCM và có thật**, có thể hỏi sâu hơn về địa danh vừa hỏi, khu vực lân cận, món ăn, lịch sử, tương lai, trải nghiệm...

10. Trả về **chỉ JSON thuần túy**, không comment, không text thừa, định dạng chính xác:
{
  "is_valid": true,
  "text": "nội dung markdown dài...",
  "suggestions": ["Câu hỏi hay 1", "Câu hỏi hay 2", "Câu hỏi hay 3", ...]
}
Hoặc khi không hợp lệ (chỉ khi HOÀN TOÀN KHÔNG liên quan TP.HCM):
{
  "is_valid": false,
  "text": "Xin lỗi, tôi chỉ hỗ trợ thông tin du lịch tại TP.HCM thôi nhé!"
}
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

def is_hcmc_related(text):
    """Kiểm tra xem text có liên quan đến TP.HCM không"""
    text_lower = text.lower()
    # Kiểm tra từ khóa TP.HCM
    for keyword in HCMC_KEYWORDS:
        if keyword in text_lower:
            return True
    # Kiểm tra các từ khóa chung có thể là TP.HCM
    general_terms = ['quận', 'district', 'phường', 'xã', 'phố', 'đường', 'street', 
                     'tòa nhà', 'building', 'chung cư', 'apartment', 'khu dân cư',
                     'trung tâm', 'center', 'siêu thị', 'supermarket', 'chợ', 'market',
                     'nhà hàng', 'restaurant', 'quán', 'shop', 'cửa hàng', 'store',
                     'khách sạn', 'hotel', 'bệnh viện', 'hospital',
                     'trường', 'school', 'đại học', 'university', 'công ty', 'company']
    has_general = any(term in text_lower for term in general_terms)
    other_provinces = ['hà nội', 'ha noi', 'đà nẵng', 'da nang', 'hải phòng', 'hai phong',
                       'cần thơ', 'can tho', 'nha trang', 'đà lạt', 'dalat', 'huế', 'hue']
    has_other = any(province in text_lower for province in other_provinces)
    return has_general and not has_other

def search_serper_images(query, context=""):
    if not SERPER_API_KEY: 
        return []
    try:
        url = "https://google.serper.dev/images"
        search_terms = [
            f"{query} TP.HCM 2025 2026",
            f"{query} Ho Chi Minh City",
            f"{query} Sài Gòn thực tế",
        ]
        if context:
            search_terms.insert(0, f"{query} {context} TP.HCM")
        
        all_images = []
        for search_q in search_terms[:2]:
            payload = json.dumps({"q": search_q, "num": 10})
            headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            data = resp.json()
            images = [{"url": i.get("imageUrl"), "caption": i.get("title", query)} 
                     for i in data.get("images", [])[:5]]
            all_images.extend(images)
            if len(all_images) >= 8:
                break
        
        seen = set()
        unique_images = []
        for img in all_images:
            if img['url'] not in seen and len(unique_images) < 8:
                seen.add(img['url'])
                unique_images.append(img)
        return unique_images
    except Exception as e:
        print(f"Image search error: {e}")
        return []

def search_serper_youtube(query, context=""):
    if not SERPER_API_KEY: 
        return []
    try:
        url = "https://google.serper.dev/videos"
        search_q = f"{query} TP.HCM du lịch trải nghiệm 2025 2026 tiếng Việt"
        if context:
            search_q = f"{query} {context} TP.HCM 2025 2026"
        payload = json.dumps({"q": search_q, "num": 10})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        links = [i.get("link") for i in data.get("videos", []) 
                if "youtube" in i.get("link", "").lower()][:4]
        return links
    except Exception as e:
        print(f"Youtube search error: {e}")
        return []

def search_serper_future_images(query=""):
    if not SERPER_API_KEY: 
        return []
    try:
        url = "https://google.serper.dev/images"
        search_q = "TP.HCM phát triển đô thị tương lai 2026 2027 2030"
        if query:
            search_q = f"{query} TP.HCM tương lai 2026 2030 phát triển"
        payload = json.dumps({"q": search_q, "num": 10})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        images = [{"url": i.get("imageUrl"), "caption": i.get("title", "Tầm nhìn TP.HCM tương lai")} 
                 for i in data.get("images", [])[:7]]
        return images
    except Exception as e:
        print(f"Future images search error: {e}")
        return []

def search_serper_future_youtube(query=""):
    if not SERPER_API_KEY: 
        return []
    try:
        url = "https://google.serper.dev/videos"
        search_q = "tương lai TP.HCM 2026 2030 phát triển đô thị hạ tầng"
        if query:
            search_q = f"{query} tương lai TP.HCM 2026 2030"
        payload = json.dumps({"q": search_q, "num": 8})
        headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        data = resp.json()
        links = [i.get("link") for i in data.get("videos", []) 
                if "youtube" in i.get("link", "").lower()][:3]
        return links
    except Exception as e:
        print(f"Future youtube search error: {e}")
        return []

@app.route("/")
def index():
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=31536000)
    return resp

@app.route("/geocode", methods=["POST"])
def geocode():
    """API để tìm tọa độ địa điểm - đảm bảo luôn tìm được nếu là TP.HCM"""
    data = request.json
    query = data.get('query', '').strip()
    
    if not query:
        return jsonify({"error": "Empty query", "found": False})
    
    # Danh sách các query variant để thử
    query_variants = [
        query,
        query + " TP.HCM",
        query + " Ho Chi Minh City",
        query + " Thành phố Hồ Chí Minh",
        query + " Sài Gòn",
        query + " Saigon",
    ]
    
    # Thêm các biến thể không dấu
    query_no_accent = query.replace('à', 'a').replace('á', 'a').replace('ả', 'a').replace('ã', 'a').replace('ạ', 'a')\
                          .replace('è', 'e').replace('é', 'e').replace('ẻ', 'e').replace('ẽ', 'e').replace('ẹ', 'e')\
                          .replace('ì', 'i').replace('í', 'i').replace('ỉ', 'i').replace('ĩ', 'i').replace('ị', 'i')\
                          .replace('ò', 'o').replace('ó', 'o').replace('ỏ', 'o').replace('õ', 'o').replace('ọ', 'o')\
                          .replace('ù', 'u').replace('ú', 'u').replace('ủ', 'u').replace('ũ', 'u').replace('ụ', 'u')\
                          .replace('ỳ', 'y').replace('ý', 'y').replace('ỷ', 'y').replace('ỹ', 'y').replace('ỵ', 'y')\
                          .replace('đ', 'd').replace('Đ', 'D')
    
    if query_no_accent != query:
        query_variants.extend([
            query_no_accent + " TP.HCM",
            query_no_accent + " Ho Chi Minh City",
        ])
    
    # Thử tìm với Nominatim
    for variant in query_variants:
        try:
            url = f"https://nominatim.openstreetmap.org/search?format=json&countrycodes=vn&q={requests.utils.quote(variant)}&addressdetails=1&namedetails=1&limit=5"
            headers = {'User-Agent': 'HCMC-Travel-AI-Guide/1.0 (contact: dev@example.com)'}
            resp = requests.get(url, headers=headers, timeout=10)
            results = resp.json()
            
            if results and len(results) > 0:
                # Tìm kết quả thuộc TP.HCM
                for result in results:
                    display_name = result.get('display_name', '').lower()
                    address = result.get('address', {})
                    
                    is_hcmc = (
                        'hồ chí minh' in display_name or
                        'ho chi minh' in display_name or
                        'sài gòn' in display_name or
                        'saigon' in display_name or
                        address.get('city', '').lower() in ['hồ chí minh', 'ho chi minh'] or
                        'thủ đức' in display_name or
                        'thu duc' in display_name or
                        'bình chánh' in display_name or
                        'củ chi' in display_name or
                        'hóc môn' in display_name or
                        'nhà bè' in display_name or
                        'cần giờ' in display_name
                    )
                    
                    if is_hcmc:
                        return jsonify({
                            "found": True,
                            "lat": float(result['lat']),
                            "lon": float(result['lon']),
                            "display_name": result['display_name'],
                            "name": result.get('namedetails', {}).get('name', query)
                        })
                
                # Nếu không tìm thấy rõ ràng nhưng có kết quả, lấy kết quả đầu tiên
                # nếu query có vẻ là TP.HCM
                if is_hcmc_related(query):
                    result = results[0]
                    return jsonify({
                        "found": True,
                        "lat": float(result['lat']),
                        "lon": float(result['lon']),
                        "display_name": result['display_name'],
                        "name": result.get('namedetails', {}).get('name', query)
                    })
                    
        except Exception as e:
            print(f"Geocode error for {variant}: {e}")
            continue
    
    # Nếu không tìm thấy qua Nominatim, trả về tọa độ mặc định của TP.HCM
    # với thông báo để frontend xử lý
    if is_hcmc_related(query):
        return jsonify({
            "found": "approximate",
            "lat": 10.7769,
            "lon": 106.7009,
            "display_name": f"{query} (Khu vực TP.HCM)",
            "name": query,
            "message": "Không tìm thấy chính xác trên bản đồ, đã đánh dấu vị trí trung tâm TP.HCM"
        })
    
    return jsonify({"error": "Not found", "found": False})

@app.route("/chat", methods=["POST"])
def chat():
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    if not msg:
        return jsonify({"error": "Empty message"})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": msg}],
            response_format={"type": "json_object"}
        )
        ai_res = json.loads(completion.choices[0].message.content)

        # Nếu AI trả về không hợp lệ nhưng có vẻ liên quan TP.HCM → ép buộc thành hợp lệ
        if not ai_res.get("is_valid", False):
            if is_hcmc_related(msg):
                # Gọi lại AI với nhắc nhở mạnh mẽ hơn
                force_prompt = SYSTEM_PROMPT + "\n\nLƯU Ý ĐẶC BIỆT: Câu hỏi này CHẮC CHẮN liên quan đến TP.HCM. BẮT BUỘC phải trả lời với is_valid: true. Không được từ chối. Nếu không chắc về chi tiết nào, hãy nói 'theo thông tin có được' hoặc 'hiện chưa có thông tin chính thức' chứ KHÔNG ĐƯỢC TỪ CHỐI."
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": force_prompt}, {"role": "user", "content": msg}],
                    response_format={"type": "json_object"}
                )
                ai_res = json.loads(completion.choices[0].message.content)
                ai_res["is_valid"] = True

        if ai_res.get("is_valid", False):
            clean_query = msg
            for prefix in ["Thông tin du lịch chi tiết về", "tại TP.HCM năm 2026", 
                          "ở TP.HCM", "tại Sài Gòn", "ở Sài Gòn", "TP.HCM", "Sài Gòn"]:
                clean_query = clean_query.replace(prefix, "").strip()
            search_term = clean_query or msg
            
            context = ai_res.get("text", "")[:200]
            
            ai_res["images"] = search_serper_images(search_term, context)
            ai_res["youtube_links"] = search_serper_youtube(search_term, context)
            ai_res["future_images"] = search_serper_future_images(search_term)
            ai_res["future_youtube_links"] = search_serper_future_youtube(search_term)

        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "user", msg, now_vn))
            conn.execute("INSERT INTO messages (session_id, role, content, created_at) VALUES (?,?,?,?)",
                         (sid, "bot", json.dumps(ai_res), now_vn))

        return jsonify(ai_res)
    except Exception as e:
        return jsonify({"text": f"Lỗi hệ thống: {str(e)}", "is_valid": False})

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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
