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
    'quận 9', 'quận 10', 'quận 11', 'quận 12', 'quận 1 ', 'quận 2 ', 'quận 3 ',
    'district 1', 'district 2', 'district 3', 'district 4', 'district 5', 'district 6',
    'district 7', 'district 8', 'district 9', 'district 10', 'district 11', 'district 12',
    # Các quận mới và đặc biệt
    'bình thạnh', 'phú nhuận', 'tân bình', 'tân phú', 'gò vấp', 'bình tân',
    'thủ đức', 'thành phố thủ đức', 'tp thủ đức', 'thu duc', 'thu duc city',
    # Các huyện
    'huyện bình chánh', 'bình chánh', 'huyện củ chi', 'củ chi', 'huyện hóc môn', 'hóc môn',
    'huyện nhà bè', 'nhà bè', 'huyện cần giờ', 'cần giờ', 'cần giờ', 'can gio',
    'huyện cần giờ', 'binh chanh', 'cu chi', 'hoc mon', 'nha be', 'can gio',
    # Các khu vực đặc biệt
    'khu đô thị mới thủ thiêm', 'thủ thiêm', 'thu thiem', 'phú mỹ hưng', 'phu my hung',
    'khu công nghệ cao', 'sài gòn hi-tech park', 'khu chế xuất', 'khu công nghiệp',
    'khu đô thị phú mỹ hưng', 'khu đô thị sala', 'khu đô thị vạn phúc',
    'trung tâm hành chính', 'khu đô thị mới',
    # Sân bay, bến xe, cảng
    'tân sơn nhất', 'tan son nhat', 'sân bay tân sơn nhất', 'sân bay quốc tế tân sơn nhất',
    'bến xe miền tây', 'ben xe mien tay', 'bến xe miền đông', 'ben xe mien dong',
    'bến xe miền đông mới', 'bến xe an sương', 'bến xe ngã tư ga',
    'cảng sài gòn', 'cang saigon', 'cảng cát lái', 'cảng vict', 'cảng phú định',
    # Các tòa nhà nổi tiếng
    'bitexco', 'bitexco financial tower', 'tháp bitexco', 'landmark 81', 'vinhomes landmark',
    'landmark81', 'vinhomes central park', 'vietcombank tower', 'saigon centre', 'saigon center',
    'takashimaya', 'saigon trade center', 'pearl plaza', 'saigon one tower',
    'mê linh point', 'melinh point', 'times square', 'saigon times square',
    'hung thinh tower', 'lim tower', 'satra', 'eximbank tower', 'sacombank tower',
    'agribank tower', 'bidv tower', 'vietinbank tower', 'techcombank tower',
    'opera view', 'the landmark', 'vincom center', 'vincom đồng khởi',
    'vincom bà triệu', 'vincom thảo điền', 'vincom mega mall', 'vincom quang trung',
    'nowzone', 'pandora', 'crescent mall', 'vivo city', 'vivocity',
    'saigon south plaza', 'parkson', 'diamond plaza', 'union square',
    # Các địa điểm du lịch
    'chợ bến thành', 'cho ben thanh', 'ben thanh market',
    'chợ lớn', 'cho lon', 'binh tay market', 'chợ bình tây',
    'dinh độc lập', 'dinh doc lap', 'independence palace', 'hội trường thống nhất',
    'nhà thờ đức bà', 'nha tho duc ba', 'notre dame cathedral', 'nhà thờ chính tòa',
    'bưu điện trung tâm', 'buu dien trung tam', 'bưu điện thành phố', 'saigon central post office',
    'bảo tàng chiến tranh', 'bao tang chien tranh', 'war remnants museum',
    'bảo tàng lịch sử', 'bao tang lich su', 'bảo tàng thành phố', 'bảo tàng mỹ thuật',
    'nhà hát lớn', 'nha hat lon', 'saigon opera house', 'nhà hát thành phố',
    'phố đi bộ nguyễn huệ', 'nguyen hue walking street', 'phố đi bộ', 'công viên 23/9',
    'công viên gia định', 'công viên lê văn tám', 'công viên văn hóa đầm sen', 'dam sen',
    'suối tiên', 'suoi tien', 'khu du lịch suối tiên', 'khu du lịch văn thánh',
    'cầu ánh sao', 'cau anh sao', 'starlight bridge', 'cầu đi bộ', 'cầu sông hàn',
    'bến bạch đằng', 'ben bach dang', 'công viên bến bạch đằng',
    'khu phố tây bùi viện', 'bui vien', 'phố tây', 'bùi viện',
    'chợ đêm', 'cho dem', 'night market',
    # Các trường đại học, bệnh viện lớn
    'đại học quốc gia', 'đhqg tp.hcm', 'đại học bách khoa', 'đại học kinh tế',
    'đại học sư phạm', 'đại học y dược', 'đại học y khoa', 'đại học luật',
    'đại học ngoại thương', 'đại học ngân hàng', 'đại học công nghiệp',
    'đại học giao thông vận tải', 'đại học sài gòn', 'đại học công nghệ thông tin',
    'đại học khoa học tự nhiên', 'đại học khoa học xã hội và nhân văn',
    'đại học kiến trúc', 'đại học mỹ thuật', 'đại học nghệ thuật', 'đại học thể dục thể thao',
    'đại học tôn đức thắng', 'đại học rmit', 'đại học quốc tế', 'đại học fulbright',
    'bệnh viện chợ rẫy', 'benh vien cho ray', 'cho ray hospital',
    'bệnh viện bình dân', 'bệnh viện 115', 'bệnh viện 175', 'bệnh viện 30/4',
    'bệnh viện nhi đồng', 'bệnh viện nhi đồng 1', 'bệnh viện nhi đồng 2',
    'bệnh viện từ dũ', 'bệnh viện hùng vương', 'bệnh viện phụ sản quốc tế',
    'bệnh viện đại học y dược', 'bệnh viện đại học quốc gia', 'bệnh viện thống nhất',
    'bệnh viện gia định', 'bệnh viện nhân dân', 'bệnh viện nhân dân gia định',
    'bệnh viện ung bướu', 'bệnh viện tim tâm đức', 'bệnh viện fv', 'bệnh viện vinmec',
    # Các địa danh lịch sử, văn hóa
    'chùa ngọc hoàng', 'chua ngoc hoang', 'jade emperor pagoda',
    'chùa bà thiên hậu', 'chua ba thien hau', 'thien hau temple',
    'chùa giác lâm', 'chua giac lam', 'chùa giác viên', 'chua giac vien',
    'chùa vĩnh nghiêm', 'chua vinh nghiem', 'chùa phật học', 'chua phat hoc',
    'chùa xá lợi', 'chua xa loi', 'thánh thất cao đài', 'thanh that cao dai',
    'nhà thờ tân định', 'nha tho tan dinh', 'pink church', 'nhà thờ màu hồng',
    'nhà thờ cha tam', 'nha tho cha tam', 'nhà thờ huyện sĩ', 'nha tho huyen si',
    'đình thần thắng nhất', 'dinh than thang nhat', 'lăng ông bà chiểu',
    'lăng tả quân lê văn duyệt', 'lang ta quan le van duyet',
    'bảo tàng chứng tích chiến tranh', 'bao tang chung tich chien tranh',
    # Các con đường, khu phố nổi tiếng
    'đồng khởi', 'dong khoi', 'lê lợi', 'le loi', 'nguyễn huệ', 'nguyen hue',
    'hàm nghi', 'ham nghi', 'tôn đức thắng', 'ton duc thang', 'lê thánh tôn',
    'pasteur', 'ly tự trọng', 'nam kỳ khởi nghĩa', 'hai bà trưng',
    'võ văn tần', 'cách mạng tháng tám', '3/2', 'ba thang hai',
    'hoàng sa', 'trường sa', 'phạm ngũ lão', 'phạm văn đồng', 'phạm văn đồng',
    'nguyễn văn trỗi', 'hoàng văn thụ', 'trần hưng đạo', 'lê văn sỹ',
    'cộng hòa', 'hoàng hoa thám', 'lạc long quân', 'võ thị sáu', 'điện biên phủ',
    'nguyễn thị minh khai', 'trường chinh', 'lý thường kiệt', 'anh thơ',
    'thảo điền', 'thao dien', 'phú mỹ hưng', 'phu my hung', 'tân phong',
    'thạnh mỹ lợi', 'thanh my loi', 'cát lái', 'cat lai', 'bình trưng đông',
    'bình trưng tây', 'phước long', 'phước bình', 'tăng nhơn phú', 'tân phú',
    'linh đông', 'linh tây', 'linh chiểu', 'linh xuân', 'bình chiểu',
    # Các khu công nghiệp, khu chế xuất
    'khu công nghiệp tân bình', 'khu công nghiệp tân thuận', 'khu công nghiệp vĩnh lộc',
    'khu công nghiệp tây bắc củ chi', 'khu công nghiệp đông nam',
    'khu chế xuất tân thuận', 'khu chế xuất linh trung', 'khu chế xuất cát lái',
    'khu công nghệ cao', 'saigon hi-tech park', 'khu r&d', 'khu nghiên cứu',
    # Các trung tâm thương mại, siêu thị
    'co.opmart', 'coopmart', 'co.op mart', 'big c', 'bigc', 'go!', 'emart',
    'lotte mart', 'aeon', 'aeon mall', 'vinmart', 'winmart', 'circle k',
    'family mart', 'ministop', 'gs25', '7-eleven', 'highlands coffee',
    'the coffee house', 'phúc long', 'trung nguyên', 'starbucks',
    # Landmark mới
    'grand marina saigon', 'grand marina', 'saigon marina', 'the river thủ thiêm',
    'empire city', 'empire city thủ thiêm', 'the opera residence',
    'metropole thủ thiêm', 'marina central', 'malaysian embassy tower',
    'tòa nhà quốc hội', 'trung tâm hành chính thủ thiêm',
    # Metro, giao thông
    'metro sài gòn', 'metro tp.hcm', 'tuyến metro số 1', 'bến thành - suối tiên',
    'metro bến thành', 'ga metro', 'nhà ga 3a', 'depot long bình',
    'cầu thủ thiêm', 'cầu phú mỹ', 'cầu sài gòn', 'cầu bình lợi', 'cầu vượt',
    'hầm thủ thiêm', 'hầm sông sài gòn', 'đại lộ đông tây', 'võ văn kiệt',
    'xa lộ hà nội', 'quốc lộ 13', 'quốc lộ 1a', 'quốc lộ 50', 'quốc lộ 22',
    'cao tốc tp.hcm - long thành - dầu giây', 'cao tốc bến lức - long thành',
    # Sân golf, khu vui chơi
    'sân golf', 'golf course', 'sân golf rạch chiếc', 'sân golf thủ đức',
    'sân golf long thành', 'khu vui chơi', 'công viên nước', 'snow town',
    'ice rink', 'sân trượt băng', 'khu vui chơi trong nhà',
    # Chợ truyền thống
    'chợ lớn', 'chợ bến thành', 'chợ tân định', 'chợ bà chiểu', 'chợ hồ thị kỷ',
    'chợ phạm văn hai', 'chợ thị nghè', 'chợ rạch ông', 'chợ an đông',
    'chợ phú lâm', 'chợ bình điền', 'chợ thủ đức', 'chợ bình triệu',
    # Các tên cũ, tên viết tắt thông dụng
    'q1', 'q2', 'q3', 'q4', 'q5', 'q6', 'q7', 'q8', 'q9', 'q10', 'q11', 'q12',
    'q.1', 'q.2', 'q.3', 'q.4', 'q.5', 'q.6', 'q.7', 'q.8', 'q.9', 'q.10', 'q.11', 'q.12',
    'bt', 'pn', 'tb', 'tp', 'gv', 'bth', 'td', 'bc', 'cc', 'hm', 'nb', 'cg',
    'h.bc', 'h.cc', 'h.hm', 'h.nb', 'h.cg',
    'd1', 'd2', 'd7', 'd9',  # district viết tắt
    'sg', 'hcm', 'hcmc',
    # Tên đường phố, địa danh nhỏ
    'hẻm', 'ngõ', 'ngách', 'hẻm số', 'đường số', 'khu phố', 'ấp', 'thôn',
    'tổ', 'khu dân cư', 'chung cư', 'căn hộ', 'nhà phố', 'biệt thự',
    'sân bay', 'bến xe', 'nhà ga', 'cảng', 'bến tàu', 'bến phà',
    'trường học', 'trường tiểu học', 'trường thcs', 'trường thpt',
    'trường mầm non', 'nhà trẻ', 'trường quốc tế', 'trường dân lập',
    'trường công lập', 'trường tư thục',
    'siêu thị', 'cửa hàng', 'nhà hàng', 'quán ăn', 'tiệm', 'shop',
    'công ty', 'văn phòng', 'tòa nhà văn phòng', 'trung tâm thương mại',
    'ngân hàng', 'bưu điện', 'trạm y tế', 'trạm xá', 'phòng khám',
    'nhà thuốc', 'hiệu thuốc', 'bệnh xá',
    'đình', 'chùa', 'miếu', 'nhà thờ', 'thánh đường', 'tu viện', 'tịnh xá',
    'cây xăng', 'trạm xăng', 'cây xăng dầu', 'trạm nhiên liệu',
    'cây atm', 'trụ atm', 'ngân hàng', 'chi nhánh ngân hàng',
    'phòng công chứng', 'văn phòng công chứng', 'trung tâm hành chính',
    'ubnd', 'ủy ban', 'phường', 'xã', 'thị trấn', 'quận', 'huyện',
    'công an', 'cảnh sát', 'trạm công an', 'trụ sở',
    'bưu cục', 'điểm bưu điện', 'trung tâm bưu chính',
    'thư viện', 'nhà văn hóa', 'trung tâm văn hóa', 'trung tâm thể thao',
    'sân vận động', 'sân bóng đá', 'sân tennis', 'hồ bơi', 'bể bơi',
    'công viên', 'vườn hoa', 'khu vui chơi', 'sân chơi',
    'bãi đậu xe', 'bãi xe', 'nhà để xe', 'trạm xe buýt', 'bến xe buýt',
    'trạm thu phí', 'trạm bot', 'cửa khẩu', 'cửa khẩu cảng', 'cảng cạn',
]

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch CHUYÊN SÂU cho TP.HCM (Thành phố Hồ Chí Minh/Sài Gòn).

QUY TẮC TUYỆT ĐỐI - PHẢI TUÂN THỦ NGHIÊM NGẶT:

1. CHỈ TỪ CHỐI khi câu hỏi HOÀN TOÀN KHÔNG liên quan đến TP.HCM. Ví dụ từ chối: "Paris", "Tokyo", "Hà Nội", "Đà Nẵng" khi không có liên kết gì đến TP.HCM.

2. BẤT KỲ địa danh, địa điểm, tòa nhà, khu vực, đường phố, chợ, bệnh viện, trường học, công ty, nhà hàng, quán ăn, khách sạn, chung cư, khu dân cư, khu công nghiệp, siêu thị, cửa hàng, ngân hàng, bưu điện, đình, chùa, nhà thờ, cơ quan nhà nước, cơ quan tư nhân... NẾU có thể liên quan đến TP.HCM (dù chỉ là khả năng nhỏ) → BẮT BUỘC phải trả lời với is_valid: true.

3. Nếu người dùng hỏi về địa điểm không rõ ràng (không ghi tỉnh/thành) nhưng TÊN giống các địa danh ở TP.HCM → Giả định là ở TP.HCM và trả lời.

4. Nếu người dùng hỏi bằng tiếng Việt không dấu → Vẫn hiểu là TP.HCM nếu tên giống.

5. Các từ khóa BẮT BUỘC coi là TP.HCM: Sài Gòn, Hồ Chí Minh, tất cả các quận (1-12, Bình Thạnh, Phú Nhuận, Tân Bình, Tân Phú, Gò Vấp, Bình Tân, Thủ Đức), tất cả các huyện (Bình Chánh, Củ Chi, Hóc Môn, Nhà Bè, Cần Giờ), Thủ Thiêm, Phú Mỹ Hưng, Bến Thành, Chợ Lớn, Bitexco, Landmark 81, và MỌI biến thể tên viết tắt, không dấu, tên cũ.

6. Nếu người dùng click vào câu hỏi gợi ý từ hệ thống → Đây là câu hỏi ĐÃ ĐƯỢC KIỂM TRA liên quan TP.HCM → BẮT BUỘC trả lời, không được từ chối.

7. Nội dung BẮT BUỘC phong phú, chi tiết (>2200 từ), dùng markdown ##, ###, ####, danh sách, *in nghiêng*, **đậm** khi phù hợp. Phải có đủ các phần sau theo đúng thứ tự:
- ## Lịch sử hình thành và phát triển (từ quá khứ → hiện tại → dự báo đến năm 2026-2030)
- ## Con người, văn hóa, lối sống đặc trưng của cư dân địa phương
- ## Ẩm thực nổi bật (liệt kê 8-12 món đặc trưng + địa chỉ cụ thể + mức giá tham khảo năm 2026)
- ## Gợi ý lịch trình du lịch chi tiết (có 3 lựa chọn: 1 ngày, 2 ngày, 3 ngày – kèm thời gian, phương tiện, chi phí ước tính)
- ## Dự báo & tầm nhìn tương lai phát triển TP.HCM đến 2026-2030 (hạ tầng, đô thị, du lịch, công nghệ, thay đổi cảnh quan…)

8. Cuối cùng BẮT BUỘC thêm mảng "suggestions": chứa 3-5 câu hỏi tiếp theo, **phải chắc chắn 100% liên quan đến TP.HCM và liên quan đến chủ đề vừa trả lời**, có thể hỏi sâu hơn về địa danh vừa hỏi, khu vực lân cận, món ăn, lịch sử, tương lai, trải nghiệm... để người dùng click tiếp tục hỏi mà không bị từ chối.

9. Trả về **chỉ JSON thuần túy**, không comment, không text thừa, định dạng chính xác:
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
                     'khách sạn', 'hotel', 'nhà nghỉ', 'bệnh viện', 'hospital',
                     'trường', 'school', 'đại học', 'university', 'công ty', 'company']
    # Nếu có từ khóa chung + không có tỉnh thành khác → coi là TP.HCM
    has_general = any(term in text_lower for term in general_terms)
    other_provinces = ['hà nội', 'ha noi', 'đà nẵng', 'da nang', 'hải phòng', 'hai phong',
                       'cần thơ', 'can tho', 'nha trang', 'đà lạt', 'dalat', 'huế', 'hue',
                       'vinh', 'hà tĩnh', 'nghệ an', 'thanh hóa', 'nam định', 'thái bình',
                       'quảng ninh', 'hạ long', 'bắc ninh', 'hưng yên', 'hải dương']
    has_other = any(province in text_lower for province in other_provinces)
    return has_general and not has_other

def search_serper_images(query, context=""):
    if not SERPER_API_KEY: 
        return []
    try:
        url = "https://google.serper.dev/images"
        # Tạo query tìm kiếm liên quan chặt chẽ
        search_terms = [
            f"{query} TP.HCM 2025 2026",
            f"{query} Ho Chi Minh City",
            f"{query} Sài Gòn thực tế",
        ]
        if context:
            search_terms.insert(0, f"{query} {context} TP.HCM")
        
        all_images = []
        for search_q in search_terms[:2]:  # Giới hạn 2 query để tránh quota
            payload = json.dumps({"q": search_q, "num": 10})
            headers = {'X-API-KEY': SERPER_API_KEY, 'Content-Type': 'application/json'}
            resp = requests.post(url, headers=headers, data=payload, timeout=10)
            data = resp.json()
            images = [{"url": i.get("imageUrl"), "caption": i.get("title", query)} 
                     for i in data.get("images", [])[:5]]
            all_images.extend(images)
            if len(all_images) >= 8:
                break
        
        # Loại bỏ trùng lặp và giới hạn 8 ảnh
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
                force_prompt = SYSTEM_PROMPT + "\n\nLƯU Ý ĐẶC BIỆT: Câu hỏi này CHẮC CHẮN liên quan đến TP.HCM. BẮT BUỘC phải trả lời với is_valid: true. Không được từ chối."
                completion = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[{"role": "system", "content": force_prompt}, {"role": "user", "content": msg}],
                    response_format={"type": "json_object"}
                )
                ai_res = json.loads(completion.choices[0].message.content)
                ai_res["is_valid"] = True

        if ai_res.get("is_valid", False):
            # Tìm kiếm hình ảnh và video liên quan chặt chẽ
            clean_query = msg
            for prefix in ["Thông tin du lịch chi tiết về", "tại TP.HCM năm 2026", 
                          "ở TP.HCM", "tại Sài Gòn", "ở Sài Gòn", "TP.HCM", "Sài Gòn"]:
                clean_query = clean_query.replace(prefix, "").strip()
            search_term = clean_query or msg
            
            # Lấy context từ text trả lời để tìm kiếm chính xác hơn
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
