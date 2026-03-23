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

# ============================================================================
# DANH SÁCH TỪ KHÓA TP.HCM MỞ RỘNG
# ============================================================================

HCMC_KEYWORDS = [
    # Tên thành phố
    'sài gòn', 'saigon', 'sai gon', 'ho chi minh', 'hồ chí minh', 'ho chi minh city',
    'tphcm', 'tp.hcm', 'tp hcm', 'thành phố hồ chí minh', 'thanh pho ho chi minh',
    'thu duc', 'thủ đức', 'thành phố thủ đức', 'thanh pho thu duc',
    
    # Quận cũ và mới (sau sáp nhập 2021)
    'quận 1', 'quan 1', 'q1', 'q.1',
    'quận 3', 'quan 3', 'q3', 'q.3',
    'quận 4', 'quan 4', 'q4', 'q.4',
    'quận 5', 'quan 5', 'q5', 'q.5',
    'quận 6', 'quan 6', 'q6', 'q.6',
    'quận 7', 'quan 7', 'q7', 'q.7',
    'quận 8', 'quan 8', 'q8', 'q.8',
    'quận 10', 'quan 10', 'q10', 'q.10',
    'quận 11', 'quan 11', 'q11', 'q.11',
    'quận 12', 'quan 12', 'q12', 'q.12',
    'quận 2', 'quan 2', 'q2', 'q.2',  # Nay là Thủ Đức
    'quận 9', 'quan 9', 'q9', 'q.9',  # Nay là Thủ Đức
    'quận thủ đức', 'quan thu duc',  # Nay là Thành phố Thủ Đức
    'phú nhuận', 'phu nhuan',
    'bình thạnh', 'binh thanh',
    'gò vấp', 'go vap',
    'tân bình', 'tan binh',
    'tân phú', 'tan phu',
    'bình tân', 'binh tan',
    
    # Huyện ngoại thành
    'bình chánh', 'binh chanh',
    'nhà bè', 'nha be',
    'hóc môn', 'hoc mon',
    'củ chi', 'cu chi',
    'cần giờ', 'can gio',
    
    # Địa danh du lịch nổi tiếng
    'chợ bến thành', 'cho ben thanh', 'ben thanh market',
    'nhà thờ đức bà', 'nha tho duc ba', 'notre dame cathedral',
    'bưu điện trung tâm', 'buu dien trung tam', 'central post office',
    'dinh độc lập', 'dinh doc lap', 'independence palace',
    'phố đi bộ nguyễn huệ', 'pho di bo nguyen hue', 'nguyen hue walking street',
    'bitexco', 'tháp bitexco', 'thap bitexco', 'bitexco financial tower',
    'landmark 81', 'vinhomes landmark', 'landmark81',
    'thảo điền', 'thao dien',
    'phú mỹ hưng', 'phu my hung',
    'bình quới', 'binh quoi',
    'chợ lớn', 'cho lon', 'chinatown',
    'cầu sài gòn', 'cau sai gon',
    'cầu phú mỹ', 'cau phu my',
    'sông sài gòn', 'song sai gon',
    'cảng sài gòn', 'cang sai gon',
    'khu phố tây', 'khu pho tay', 'bùi viện', 'bui vien', 'phạm ngũ lão', 'pham ngu lao',
    
    # Chợ truyền thống
    'chợ tân định', 'cho tan dinh',
    'chợ bình tây', 'cho binh tay',
    'chợ an đông', 'cho an dong',
    'chợ hòa bình', 'cho hoa binh',
    
    # Công viên, khu vui chơi
    'thảo cầm viên', 'thao cam vien', 'saigon zoo',
    'công viên gia định', 'cong vien gia dinh',
    'công viên lê văn tám', 'cong vien le van tam',
    'công viên tao đàn', 'cong vien tao dan',
    'suối tiên', 'suoi tien',
    'đầm sen', 'dam sen',
    
    # Bảo tàng, di tích
    'bảo tàng chiến tranh', 'bao tang chien tranh', 'war remnants museum',
    'bảo tàng thành phố', 'bao tang thanh pho',
    'bảo tàng lịch sử', 'bao tang lich su',
    'bảo tàng mỹ thuật', 'bao tang my thuat',
    'lăng ông bà chiểu', 'lang ong ba chieu',
    'chùa giác lâm', 'chua giac lam',
    'chùa ngọc hoàng', 'chua ngoc hoang',
    'nhà thờ tân định', 'nha tho tan dinh',
    
    # Trung tâm thương mại
    'vincom', 'vincom center', 'vincom plaza',
    'aeon', 'aeon mall',
    'crescent mall',
    'vivocity', 'vivo city',
    'takashimaya',
    'saigon centre',
    'nowzone',
    'union square',
    'diamond plaza',
    'parkson',
    'lotte mart',
    'big c', 'go!',
    'co.opmart', 'coopmart',
    'mega market',
    'emart',
    'gigamall',
    'thiso',
    
    # Tòa nhà văn phòng
    'tòa nhà bitexco', 'toa nha bitexco',
    'tòa nhà landmark', 'toa nha landmark',
    'tòa nhà văn phòng', 'toa nha van phong',
    'saigon one tower',
    'lim tower',
    'ab tower',
    'sunwah tower',
    'saigon tower',
    'deutsches haus',
    'vietcombank tower',
    'bidv tower',
    
    # Khách sạn nổi tiếng (chọn lọc, không lặp)
    'khách sạn rex', 'rex hotel',
    'khách sạn caravelle', 'caravelle',
    'khách sạn continental', 'continental',
    'khách sạn majestic', 'majestic',
    'khách sạn park hyatt', 'park hyatt',
    'khách sạn sheraton', 'sheraton',
    'khách sạn intercontinental', 'intercontinental',
    'khách sạn pullman', 'pullman',
    'khách sạn novotel', 'novotel',
    'khách sạn sofitel', 'sofitel',
    'khách sạn hilton', 'hilton',
    'khách sạn marriott', 'marriott',
    'khách sạn new world', 'new world',
    'khách sạn windsor plaza', 'windsor plaza',
    'khách sạn tân sơn nhất', 'tan son nhat hotel',
    
    # Sân bay, bến xe, cảng
    'tân sơn nhất', 'tan son nhat', 'sân bay', 'san bay',
    'bến xe miền tây', 'ben xe mien tay',
    'bến xe miền đông', 'ben xe mien dong',
    'bến xe an sương', 'ben xe an suong',
    'cảng', 'cang', 'bến tàu', 'ben tau',
    
    # Trường đại học, cao đẳng
    'đại học quốc gia', 'dai hoc quoc gia', 'đhqg',
    'đại học bách khoa', 'dai hoc bach khoa',
    'đại học kinh tế', 'dai hoc kinh te',
    'đại học sư phạm', 'dai hoc su pham',
    'đại học y dược', 'dai hoc y duoc',
    'đại học luật', 'dai hoc luat',
    'đại học ngân hàng', 'dai hoc ngan hang',
    'đại học ngoại thương', 'dai hoc ngoai thuong',
    'đại học công nghiệp', 'dai hoc cong nghiep',
    'đại học giao thông vận tải', 'dai hoc giao thong van tai',
    'đại học mở', 'dai hoc mo',
    'đại học tôn đức thắng', 'dai hoc ton duc thang',
    'đại học rmit', 'dai hoc rmit',
    'đại học quốc tế', 'dai hoc quoc te',
    
    # Bệnh viện lớn
    'bệnh viện chợ rẫy', 'benh vien cho ray', 'cho ray hospital',
    'bệnh viện 115', 'benh vien 115',
    'bệnh viện 175', 'benh vien 175',
    'bệnh viện bình dân', 'benh vien binh dan',
    'bệnh viện đại học y dược', 'benh vien dai hoc y duoc',
    'bệnh viện fv', 'benh vien fv',
    'bệnh viện từ dũ', 'benh vien tu du',
    'bệnh viện hùng vương', 'benh vien hung vuong',
    'bệnh viện nhi đồng', 'benh vien nhi dong',
    'bệnh viện ung bướu', 'benh vien ung buou',
    'bệnh viện tim', 'benh vien tim',
    'bệnh viện mắt', 'benh vien mat',
    'bệnh viện tai mũi họng', 'benh vien tai mui hong',
    
    # Cơ quan nhà nước
    'ubnd', 'ủy ban nhân dân', 'uy ban nhan dan',
    'hđnd', 'hội đồng nhân dân', 'hoi dong nhan dan',
    'sở gtvt', 'so gtvt',
    'sở y tế', 'so y te',
    'sở giáo dục', 'so giao duc',
    'sở tài chính', 'so tai chinh',
    'sở xây dựng', 'so xay dung',
    'công an', 'cong an', 'cảnh sát', 'canh sat',
    'tòa án', 'toa an',
    'viện kiểm sát', 'vien kiem sat',
    'chi cục thuế', 'chi cuc thue',
    'trung tâm hành chính', 'trung tam hanh chinh',
    
    # Khu đô thị, khu công nghiệp mới
    'thủ thiêm', 'thu thiem',
    'khu đô thị mới', 'khu do thi moi',
    'khu công nghệ cao', 'khu cong nghe cao',
    'khu chế xuất', 'khu che xuat', 'kcx',
    'khu công nghiệp', 'khu cong nghiep', 'kcn',
    'khu dân cư', 'khu dan cu',
    'metro', 'tuyến metro', 'tuyen metro',
    'bến thành suối tiên', 'ben thanh suoi tien',
    'bến thành tham lương', 'ben thanh tham luong',
    
    # Đường phố chính
    'nguyễn huệ', 'nguyen hue',
    'lê lợi', 'le loi',
    'đồng khởi', 'dong khoi',
    'hàm nghi', 'ham nghi',
    'nam kỳ khởi nghĩa', 'nam ky khoi nghia',
    'pasteur',
    'lý tự trọng', 'ly tu trong',
    'phạm ngũ lão', 'pham ngu lao',
    'bùi viện', 'bui vien',
    'trần hưng đạo', 'tran hung dao',
    'nguyễn trãi', 'nguyen trai',
    'cách mạng tháng 8', 'cach mang thang 8',
    '3/2', 'ba thang hai',
    'hoàng văn thụ', 'hoang van thu',
    'phạm văn đồng', 'pham van dong',
    'võ văn kiệt', 'vo van kiet',
    'mai chí thọ', 'mai chi tho',
    'xa lộ hà nội', 'xa lo ha noi',
    'nguyễn văn linh', 'nguyen van linh',
    'nguyễn hữu thọ', 'nguyen huu tho',
    'cộng hòa', 'cong hoa',
    'trường sơn', 'truong son',
    
    # Phường/xã thường gặp (sau sáp nhập)
    'phường bến nghé', 'phuong ben nghe',
    'phường bến thành', 'phuong ben thanh',
    'phường nguyễn thái bình', 'phuong nguyen thai binh',
    'phường cầu kho', 'phuong cau kho',
    'phường cầu ông lãnh', 'phuong cau ong lanh',
    'phường đa kao', 'phuong da kao',
    'phường tân định', 'phuong tan dinh',
    'phường phạm ngũ lão', 'phuong pham ngu lao',
    'phường cô giang', 'phuong co giang',
    'phường nguyễn cư trinh', 'phuong nguyen cu trinh',
    'phường an phú', 'phuong an phu',
    'phường thảo điền', 'phuong thao dien',
    'phường bình an', 'phuong binh an',
    'phường bình trưng đông', 'phuong binh trung dong',
    'phường bình trưng tây', 'phuong binh trung tay',
    'phường cát lái', 'phuong cat lai',
    'phường thạnh mỹ lợi', 'phuong thanh my loi',
    'phường thủ thiêm', 'phuong thu thiem',
    'phường linh chiểu', 'phuong linh chieu',
    'phường linh đông', 'phuong linh dong',
    'phường linh tây', 'phuong linh tay',
    'phường linh trung', 'phuong linh trung',
    'phường linh xuân', 'phuong linh xuan',
    'phường bình chiểu', 'phuong binh chieu',
    'phường bình thọ', 'phuong binh tho',
    'phường hiệp bình chánh', 'phuong hiep binh chanh',
    'phường hiệp bình phước', 'phuong hiep binh phuoc',
    'phường long bình', 'phuong long binh',
    'phường long phước', 'phuong long phuoc',
    'phường long thạnh mỹ', 'phuong long thanh my',
    'phường long trường', 'phuong long truong',
    'phường phú hữu', 'phuong phu huu',
    'phường phước bình', 'phuong phuoc binh',
    'phường phước long a', 'phuong phuoc long a',
    'phường phước long b', 'phuong phuoc long b',
    'phường tăng nhơn phú a', 'phuong tang nhon phu a',
    'phường tăng nhơn phú b', 'phuong tang nhon phu b',
    'phường trường thạnh', 'phuong truong thanh',
    
    # Tên viết tắt, không dấu phổ biến
    'ks', 'khach san', 'khách sạn',
    'bv', 'benh vien', 'bệnh viện',
    'dh', 'dai hoc', 'đại học',
    'cd', 'cao dang', 'cao đẳng',
    'th', 'tieu hoc', 'tiểu học',
    'thcs', 'trung hoc co so', 'trung học cơ sở',
    'thpt', 'trung hoc pho thong', 'trung học phổ thông',
    'cty', 'cong ty', 'công ty',
    'vp', 'van phong', 'văn phòng',
    'nh', 'ngan hang', 'ngân hàng',
    'ch', 'cua hang', 'cửa hàng',
    'si', 'sieu thi', 'siêu thị',
    'nx', 'nha xuat ban', 'nhà xuất bản',
    'bx', 'ben xe', 'bến xe',
    'sb', 'san bay', 'sân bay',
    'cg', 'cang', 'cảng',
    'ub', 'uy ban', 'ủy ban',
    'so', 'sở',
    'pvc', 'phuong', 'phường',
    'xa', 'xã',
    'tt', 'thi tran', 'thị trấn',
    'kdc', 'khu dan cu', 'khu dân cư',
    'kcn', 'khu cong nghiep', 'khu công nghiệp',
    'kcx', 'khu che xuat', 'khu chế xuất',
    'cc', 'chung cu', 'chung cư',
    'cn', 'can ho', 'căn hộ',
    'bt', 'biet thu', 'biệt thự',
    'np', 'nha pho', 'nhà phố',
    'mb', 'mat bang', 'mặt bằng',
    'kd', 'kinh doanh',
    'tm', 'thuong mai', 'thương mại',
    'dv', 'dich vu', 'dịch vụ',
    'sx', 'san xuat', 'sản xuất',
    'vt', 'van tai', 'vận tải',
    'xh', 'xa hoi', 'xã hội',
    'yt', 'y te', 'y tế',
    'gd', 'giao duc', 'giáo dục',
    'vh', 'van hoa', 'văn hóa',
    'tt', 'the thao', 'thể thao',
    'sk', 'suc khoe', 'sức khỏe',
    'an', 'an ninh',
    'qp', 'quoc phong', 'quốc phòng',
    'ng', 'ngoai giao', 'ngoại giao',
    'kt', 'kinh te', 'kinh tế',
    'tc', 'tai chinh', 'tài chính',
    'xd', 'xay dung', 'xây dựng',
    'gt', 'giao thong', 'giao thông',
    'bc', 'bao chi', 'báo chí',
    'tt', 'truyen thong', 'truyền thông',
    'cntt', 'cong nghe thong tin', 'công nghệ thông tin',
    'vhtt', 'van hoa the thao', 'văn hóa thể thao',
    'dtdc', 'dien thoai di dong', 'điện thoại di động',
    'vien thong', 'viễn thông',
    'bdt', 'bat dong san', 'bất động sản',
    'xd', 'xay dung', 'xây dựng',
    'ck', 'chung khoan', 'chứng khoán',
    'nh', 'nha hang', 'nhà hàng',
    'cf', 'ca phe', 'cà phê',
    'ts', 'tra sua', 'trà sữa',
    'an', 'an uong', 'ăn uống',
    'nn', 'nong nghiep', 'nông nghiệp',
    'cn', 'cong nghiep', 'công nghiệp',
    'tm', 'thuong mai', 'thương mại',
    'dv', 'du lich', 'du lịch',
    'lh', 'lu hanh', 'lữ hành',
    'kh', 'khach san', 'khách sạn',
    'nha nghi', 'nhà nghỉ',
    'ct', 'cong trinh', 'công trình',
    'da', 'du an', 'dự án',
    'cp', 'co phan', 'cổ phần',
    'tnhh', 'trach nhiem huu han', 'trách nhiệm hữu hạn',
    'tn', 'tu nhan', 'tư nhân',
    'nn', 'nha nuoc', 'nhà nước',
    'tw', 'trung uong', 'trung ương',
    'tinh', 'tỉnh',
    'tp', 'thanh pho', 'thành phố',
    'tptd', 'thanh pho thu duc', 'thành phố thủ đức',
]

# ============================================================================
# SYSTEM PROMPT CHO AI
# ============================================================================

SYSTEM_PROMPT = """Bạn là chuyên gia du lịch và thông tin địa lý TP.HCM (Thành phố Hồ Chí Minh / Sài Gòn).

QUY TẮC TUYỆT ĐỐI:
1. Mọi câu hỏi về địa danh, tòa nhà, đường phố, cơ quan, trường học, bệnh viện, chợ, siêu thị, quán ăn, nhà hàng, công ty, khu công nghiệp, công viên, bến xe, sân bay, cảng, cầu, sông, kênh rạch, di tích, đền chùa, nhà thờ... đều PHẢI trả lời với is_valid: true

2. Giả định TẤT CẢ địa danh không rõ ràng đều thuộc TP.HCM (vì đây là app chuyên về TP.HCM)

3. Chấp nhận mọi cách viết: có dấu, không dấu, viết tắt, tên cũ (Quận 2, Quận 9 = Thủ Đức)

4. Định dạng địa chỉ theo đơn vị hành chính MỚI (sau sáp nhập 2021):
   - Phường/Khu phố → Thành phố Thủ Đức (nếu thuộc Thủ Đức) HOẶC TP. Hồ Chí Minh
   - KHÔNG dùng "Quận", "Huyện" trong địa chỉ hiển thị
   - Ví dụ: "Phường Bến Thành, TP. Hồ Chí Minh" hoặc "Phường Thảo Điền, Thành phố Thủ Đức"

5. Trả về JSON:
{
  "is_valid": true,
  "text": "nội dung markdown chi tiết...",
  "suggestions": ["câu hỏi liên quan TP.HCM 1", "câu hỏi liên quan TP.HCM 2", "câu hỏi liên quan TP.HCM 3"]
}

Nội dung bắt buộc:
- ## Tổng quan và vị trí (địa chỉ theo đơn vị hành chính mới)
- ## Lịch sử hình thành (quá khứ → hiện tại → 2026-2030)
- ## Đặc điểm nổi bật và ý nghĩa
- ## Ẩm thực xung quanh (5-8 món + địa chỉ cụ thể + giá tham khảo 2026)
- ## Hoạt động và trải nghiệm gợi ý
- ## Thông tin thực tế (giờ mở cửa, giá vé, cách di chuyển)
- ## Dự báo phát triển đến 2026-2030

Lưu ý: suggestions phải CHẮC CHẮN liên quan đến TP.HCM và AI có thể trả lời được."""

# ============================================================================
# DATABASE
# ============================================================================

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

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def is_hcmc_related(query):
    """Kiểm tra nhanh xem query có liên quan TP.HCM không"""
    query_lower = query.lower()
    for keyword in HCMC_KEYWORDS:
        if keyword in query_lower:
            return True
    # Nếu query ngắn, giả định là TP.HCM
    if len(query.split()) <= 3:
        return True
    return True  # Mặc định chấp nhận tất cả

def format_address_new_admin_unit(address_data, display_name):
    """
    Định dạng địa chỉ theo đơn vị hành chính mới 2021:
    Phường → Thành phố Thủ Đức (nếu thuộc Thủ Đức) hoặc TP. Hồ Chí Minh
    Không dùng Quận/Huyện trong địa chỉ hiển thị
    """
    parts = []
    
    # Tên địa điểm
    name = address_data.get('name', '') or display_name.split(',')[0]
    
    # Xác định khu vực
    suburb = address_data.get('suburb', '')
    neighbourhood = address_data.get('neighbourhood', '')
    quarter = address_data.get('quarter', '')
    city_district = address_data.get('city_district', '')
    city = address_data.get('city', '')
    town = address_data.get('town', '')
    
    # Kiểm tra có thuộc Thủ Đức không
    is_thu_duc = False
    thu_duc_indicators = ['thủ đức', 'thu duc', 'quận 2', 'quận 9', 'quận thủ đức']
    
    check_string = f"{display_name} {city_district} {city} {town} {suburb}".lower()
    for indicator in thu_duc_indicators:
        if indicator in check_string:
            is_thu_duc = True
            break
    
    # Thêm phường/khu phố
    if suburb and 'phường' in suburb.lower():
        parts.append(suburb)
    elif neighbourhood and 'phường' in neighbourhood.lower():
        parts.append(neighbourhood)
    elif quarter and 'phường' in quarter.lower():
        parts.append(quarter)
    elif suburb:
        parts.append(f"Khu vực {suburb}")
    elif neighbourhood:
        parts.append(f"Khu vực {neighbourhood}")
    
    # Thêm thành phố cấp trên
    if is_thu_duc:
        parts.append('Thành phố Thủ Đức')
    else:
        # Kiểm tra các quận còn lại
        quận_maintained = ['1', '3', '4', '5', '6', '7', '8', '10', '11', '12', 
                          'bình tân', 'bình thạnh', 'gò vấp', 'phú nhuận', 'tân bình', 'tân phú']
        
        found_quan = None
        for q in quận_maintained:
            if f'quận {q}' in check_string or f'quan {q}' in check_string:
                found_quan = q
                break
        
        if found_quan:
            # Các quận này giờ là phường trực thuộc TP.HCM
            parts.append('TP. Hồ Chí Minh')
        else:
            parts.append('TP. Hồ Chí Minh')
    
    # Thêm quốc gia nếu cần
    if address_data.get('country'):
        parts.append(address_data['country'])
    
    # Lọc bỏ các phần trùng lặp và rỗng
    filtered_parts = []
    seen = set()
    for p in parts:
        p_clean = p.strip()
        if p_clean and p_clean.lower() not in seen and p_clean != 'Việt Nam':
            seen.add(p_clean.lower())
            filtered_parts.append(p_clean)
    
    if not filtered_parts:
        return "TP. Hồ Chí Minh, Việt Nam"
    
    result = ', '.join(filtered_parts)
    if 'Việt Nam' not in result:
        result += ', Việt Nam'
    
    return result

def search_serper_images(query, context=""):
    """Tìm kiếm hình ảnh liên quan đến query"""
    if not SERPER_API_KEY:
        return []
    try:
        search_query = f"{query} TP.HCM Ho Chi Minh City 2024 2025 2026"
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
        print(f"[Serper Images] Error: {e}")
        return []

def search_serper_youtube(query, context=""):
    """Tìm kiếm video YouTube liên quan"""
    if not SERPER_API_KEY:
        return []
    try:
        search_query = f"{query} TP.HCM Sài Gòn du lịch trải nghiệm 2024 2025 2026"
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
        print(f"[Serper YouTube] Error: {e}")
        return []

def search_serper_future_images(query=""):
    """Tìm kiếm hình ảnh về tương lai TP.HCM"""
    if not SERPER_API_KEY:
        return []
    try:
        search_terms = [
            "TP.HCM phát triển 2026 2030",
            "Sài Gòn tương lai metro",
            "Thủ Đức thành phố tương lai",
            "Ho Chi Minh City future development 2030"
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
        print(f"[Future Images] Error: {e}")
        return []

def search_serper_future_youtube():
    """Tìm kiếm video về tương lai TP.HCM"""
    if not SERPER_API_KEY:
        return []
    try:
        search_terms = [
            "tương lai TP.HCM 2026 2030",
            "Sài Gòn phát triển đô thị metro",
            "Thủ Thiêm tương lai",
            "Ho Chi Minh City future 2030"
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
        print(f"[Future YouTube] Error: {e}")
        return []

def get_ai_response(client, messages):
    """Gọi API Groq để lấy phản hồi từ AI"""
    try:
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4000
        )
        
        content = completion.choices[0].message.content
        data = json.loads(content)
        
        # Ép buộc is_valid = true
        data["is_valid"] = True
        
        return data
            
    except Exception as e:
        print(f"[AI] Error: {e}")
        return {
            "is_valid": True,
            "text": f"Thông tin về địa điểm tại TP.HCM. [Đang cập nhật dữ liệu chi tiết...]",
            "suggestions": [
                "Các địa điểm nổi tiếng khác ở TP.HCM",
                "Ẩm thực đặc trưng Sài Gòn",
                "Phát triển tương lai của TP.HCM 2026-2030"
            ]
        }

def generate_safe_suggestions(query):
    """Tạo gợi ý câu hỏi an toàn, chắc chắn liên quan TP.HCM"""
    query_lower = query.lower() if query else ""
    
    # Mặc định
    defaults = [
        "Các địa điểm du lịch nổi tiếng ở TP.HCM 2026",
        "Ẩm thực đường phố Sài Gòn phải thử",
        "Thành phố Thủ Đức sau sáp nhập có gì mới"
    ]
    
    # Theo chủ đề
    if any(x in query_lower for x in ['ăn', 'an', 'món', 'food', 'quán', 'nhà hàng']):
        return [
            "Các món đặc sản Sài Gòn phải thử 2026",
            "Quán ăn đêm nổi tiếng ở TP.HCM",
            "Chợ ẩm thực và đường phố Sài Gòn"
        ]
    
    if any(x in query_lower for x in ['chợ', 'cho', 'siêu thị', 'sieu thi', 'mall']):
        return [
            "Chợ truyền thống nổi tiếng ở TP.HCM",
            "Trung tâm thương mại mới nhất Sài Gòn",
            "Chợ đêm và chợ phiên ở TP.HCM"
        ]
    
    if any(x in query_lower for x in ['bệnh viện', 'bv', 'benh vien', 'hospital']):
        return [
            "Các bệnh viện lớn tại TP.HCM",
            "Bệnh viện quốc tế tại Sài Gòn",
            "Phòng khám và y tế tại TP.HCM"
        ]
    
    if any(x in query_lower for x in ['trường', 'truong', 'đại học', 'dai hoc', 'school']):
        return [
            "Các trường đại học top đầu TP.HCM",
            "Hệ thống giáo dục tại Sài Gòn",
            "Trường quốc tế tại TP.HCM"
        ]
    
    if any(x in query_lower for x in ['khách sạn', 'ks', 'khach san', 'hotel']):
        return [
            "Khách sạn 5 sao tại TP.HCM",
            "Khách sạn boutique độc đáo ở Sài Gòn",
            "Khách sạn gần trung tâm TP.HCM"
        ]
    
    if any(x in query_lower for x in ['tòa nhà', 'toa nha', 'building', 'văn phòng']):
        return [
            "Các tòa nhà cao nhất Sài Gòn hiện nay",
            "Tòa nhà văn phòng hạng A tại TP.HCM",
            "Kiến trúc hiện đại tại TP.HCM"
        ]
    
    if any(x in query_lower for x in ['công viên', 'cong vien', 'park']):
        return [
            "Công viên xanh tại TP.HCM",
            "Khu vui chơi giải trí ở Sài Gòn",
            "Công viên nước và giải trí tại TP.HCM"
        ]
    
    if any(x in query_lower for x in ['metro', 'tàu điện', 'tau dien', 'tuyến metro']):
        return [
            "Tuyến Metro Bến Thành - Suối Tiên",
            "Tuyến Metro Bến Thành - Tham Lương",
            "Phát triển giao thông công cộng TP.HCM 2026"
        ]
    
    if any(x in query_lower for x in ['thủ đức', 'thu duc', 'quận 2', 'quận 9']):
        return [
            "Thành phố Thủ Đức sau sáp nhập 2021",
            "Khu công nghệ cao Thủ Đức",
            "Thủ Thiêm và tương lai Thành phố Thủ Đức"
        ]
    
    return defaults

def validate_suggestions(suggestions):
    """Đảm bảo tất cả suggestions đều liên quan TP.HCM"""
    if not suggestions:
        return generate_safe_suggestions("")
    
    validated = []
    hcmc_terms = ['tp.hcm', 'tphcm', 'sài gòn', 'saigon', 'hồ chí minh', 'ho chi minh', 
                  'thủ đức', 'thu duc', 'thành phố thủ đức']
    
    for s in suggestions[:3]:
        if not s:
            continue
        s_lower = s.lower()
        if any(term in s_lower for term in hcmc_terms):
            validated.append(s)
        else:
            validated.append(f"{s} tại TP.HCM")
    
    while len(validated) < 3:
        validated.append("Khám phá thêm địa điểm ở Sài Gòn")
    
    return validated[:3]

# ============================================================================
# ROUTES
# ============================================================================

@app.route("/")
def index():
    """Trang chủ"""
    sid = request.cookies.get("session_id") or str(uuid.uuid4())
    resp = make_response(render_template("index.html"))
    resp.set_cookie("session_id", sid, httponly=True, max_age=31536000)
    return resp

@app.route("/chat", methods=["POST"])
def chat():
    """API chat với AI"""
    sid = request.cookies.get("session_id")
    msg = request.json.get("msg", "").strip()
    
    if not msg:
        return jsonify({"error": "Empty message", "is_valid": True})

    try:
        client = Groq(api_key=GROQ_API_KEY)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": msg}
        ]
        
        ai_res = get_ai_response(client, messages)
        
        # Luôn đảm bảo is_valid = true
        ai_res["is_valid"] = True
        
        # Tìm kiếm media
        ai_res["images"] = search_serper_images(msg, msg[:50])
        ai_res["youtube_links"] = search_serper_youtube(msg, msg[:50])
        ai_res["future_images"] = search_serper_future_images(msg)
        ai_res["future_youtube_links"] = search_serper_future_youtube()
        
        # Xử lý suggestions
        if not ai_res.get("suggestions") or len(ai_res["suggestions"]) < 3:
            ai_res["suggestions"] = generate_safe_suggestions(msg)
        else:
            ai_res["suggestions"] = validate_suggestions(ai_res["suggestions"])
        
        # Lưu vào database
        now_vn = datetime.now(VN_TZ).strftime("%H:%M %d/%m/%Y")
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
        print(f"[Chat] Error: {e}")
        # Trả về response an toàn ngay cả khi lỗi
        return jsonify({
            "text": f"Thông tin về '{msg}' tại TP.HCM. Hệ thống đang cập nhật dữ liệu chi tiết...", 
            "is_valid": True,
            "suggestions": generate_safe_suggestions(msg),
            "images": search_serper_images(msg),
            "youtube_links": search_serper_youtube(msg),
            "future_images": search_serper_future_images(),
            "future_youtube_links": search_serper_future_youtube()
        })

@app.route("/history")
def get_history():
    """Lấy lịch sử chat"""
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
    """Xóa lịch sử chat"""
    sid = request.cookies.get("session_id")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (sid,))
    return jsonify({"status": "ok"})

@app.route("/export_pdf")
def export_pdf():
    """Xuất lịch sử chat ra PDF"""
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
    """API tìm kiếm địa điểm trên bản đồ"""
    data = request.json
    query = data.get("query", "").strip()
    
    if not query:
        return jsonify({"error": "Empty query", "results": []})
    
    results = search_nominatim_extended(query)
    return jsonify({"results": results})

def search_nominatim_extended(query):
    """
    Tìm kiếm địa điểm qua Nominatim với nhiều biến thể
    Trả về địa chỉ theo đơn vị hành chính mới (Phường → TP/Thành phố)
    """
    query_lower = query.lower()
    
    # Map tên cũ sang tên mới sau sáp nhập
    old_to_new = {
        'quận 2': 'Thành phố Thủ Đức',
        'quan 2': 'Thành phố Thủ Đức',
        'q2': 'Thành phố Thủ Đức',
        'q.2': 'Thành phố Thủ Đức',
        'quận 9': 'Thành phố Thủ Đức',
        'quan 9': 'Thành phố Thủ Đức',
        'q9': 'Thành phố Thủ Đức',
        'q.9': 'Thành phố Thủ Đức',
        'quận thủ đức': 'Thành phố Thủ Đức',
        'quan thu duc': 'Thành phố Thủ Đức',
        'huyện thủ đức': 'Thành phố Thủ Đức',
        'huyen thu duc': 'Thành phố Thủ Đức',
    }
    
    # Xác định tên thay thế
    normalized_query = query
    for old, new in old_to_new.items():
        if old in query_lower:
            normalized_query = new
            break
    
    # Tạo các biến thể tìm kiếm
    variants = [
        query,
        normalized_query,
        f"{query}, TP.HCM, Vietnam",
        f"{query}, Ho Chi Minh City",
        f"{query}, Thành phố Hồ Chí Minh",
        f"{query}, Thành phố Thủ Đức",
        f"{query}, Sài Gòn",
        f"{query}, Quận 1, TP.HCM",
        f"{query}, Quận 7, TP.HCM",
        f"{query}, Quận 3, TP.HCM",
    ]
    
    # Thêm biến thể không dấu nếu query không có dấu
    if not any(ord(c) > 127 for c in query):
        variants.extend([
            f"{query} Thanh pho Ho Chi Minh",
            f"{query} Thu Duc",
        ])
    
    all_results = []
    seen_coords = set()
    
    headers = {
        'User-Agent': 'HCMC-Travel-AI-Guide/1.0 (contact: hcmc-guide@example.com)',
        'Accept-Language': 'vi,en'
    }
    
    for variant in variants:
        try:
            encoded = requests.utils.quote(variant)
            url = f"https://nominatim.openstreetmap.org/search?format=json&countrycodes=vn&q={encoded}&addressdetails=1&namedetails=1&limit=5"
            
            print(f"[Nominatim] Query: {variant}")
            
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code != 200:
                print(f"[Nominatim] HTTP {res.status_code}")
                continue
                
            data = res.json()
            
            for item in data:
                display_name = item.get('display_name', '')
                address = item.get('address', {})
                
                # Kiểm tra có phải TP.HCM không
                check_str = f"{display_name} {address.get('city', '')} {address.get('town', '')}".lower()
                
                is_hcmc = (
                    'thành phố hồ chí minh' in check_str or
                    'ho chi minh city' in check_str or
                    'hồ chí minh' in check_str or
                    'thu duc' in check_str or
                    'thủ đức' in check_str or
                    'quận' in check_str or
                    address.get('city') in ['Thành phố Hồ Chí Minh', 'Ho Chi Minh City']
                )
                
                # Nếu query xuất hiện trong tên, chấp nhận luôn
                if not is_hcmc and query_lower in display_name.lower():
                    is_hcmc = True
                
                if is_hcmc:
                    lat = round(float(item['lat']), 6)
                    lon = round(float(item['lon']), 6)
                    coord_key = f"{lat},{lon}"
                    
                    if coord_key not in seen_coords:
                        seen_coords.add(coord_key)
                        
                        # Format địa chỉ theo đơn vị hành chính mới
                        formatted_address = format_address_new_admin_unit(address, display_name)
                        
                        name = item.get('namedetails', {}).get('name') or display_name.split(',')[0]
                        
                        all_results.append({
                            'lat': lat,
                            'lon': lon,
                            'display_name': formatted_address,
                            'name': name,
                            'type': item.get('type', 'unknown'),
                            'importance': item.get('importance', 0)
                        })
                        print(f"[Nominatim] Added: {name} at {formatted_address}")
            
            if len(all_results) >= 5:
                break
                
        except Exception as e:
            print(f"[Nominatim] Error: {e}")
            continue
    
    # Sắp xếp theo importance
    all_results.sort(key=lambda x: x['importance'], reverse=True)
    
    print(f"[Nominatim] Total results: {len(all_results)}")
    return all_results[:8]

# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000, debug=False)
