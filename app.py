from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os
import re

app = Flask(__name__)

def clean_and_format(raw_text, query):
    """
    Hàm này đóng vai trò 'Bộ não' thay thế AI:
    Nó sẽ lọc dữ liệu thô, loại bỏ rác và định dạng lại thành các mục chuyên nghiệp.
    """
    if not raw_text:
        return "Xin lỗi, không tìm thấy dữ liệu cụ thể cho địa danh này."

    # Chia nhỏ dữ liệu dựa trên dấu phân cách
    parts = raw_text.split('|')
    
    # Tạo cấu trúc bài viết
    formatted_html = f"<h3>🌟 Khám phá du lịch: {query.upper()}</h3><br>"
    
    # Mục 1: Tổng quan (Lấy đoạn đầu tiên cào được)
    formatted_html += f"<b>📍 Tổng quan:</b><br>{parts[0].strip()}<br><br>"
    
    # Mục 2: Văn hóa & Đặc điểm (Lấy các đoạn tiếp theo)
    if len(parts) > 1:
        formatted_html += f"<b>🏛️ Văn hóa & Cảnh quan:</b><br><ul>"
        for p in parts[1:3]:
            if len(p) > 20:
                formatted_html += f"<li>{p.strip()}</li>"
        formatted_html += "</ul><br>"
        
    # Mục 3: Ẩm thực & Kinh nghiệm (Đoạn cuối)
    if len(parts) > 3:
        formatted_html += f"<b>🍲 Ẩm thực & Lời khuyên:</b><br>{parts[3].strip()}<br>"

    return formatted_html

def search_google_all_in_one(query):
    try:
        with sync_playwright() as p:
            # Khởi chạy trình duyệt với cấu hình Cloud
            browser = p.chromium.launch(
                headless=True, 
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            # --- 1. LẤY THÔNG TIN VĂN BẢN VÀ VIDEO ---
            search_url = f"https://www.google.com/search?q={query}+travel+guide+vietnam"
            page.goto(search_url, timeout=60000)
            
            # Cào dữ liệu văn bản (lấy các thẻ div mô tả của Google)
            texts = page.evaluate('''() => {
                let items = Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 5);
                return items.map(el => el.innerText).join(' | ');
            }''')
            
            # Lấy link YouTube đầu tiên
            yt_link = page.evaluate('''() => {
                const link = document.querySelector('a[href*="youtube.com/watch"]');
                return link ? link.href : "";
            }''')

            # --- 2. LẤY HÌNH ẢNH THỰC TẾ ---
            img_url = f"https://www.google.com/search?q={query}+vietnam+tourism+photography&tbm=isch"
            page.goto(img_url, timeout=60000)
            # Đợi ảnh load một chút
            page.wait_for_timeout(2000)
            images = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img'))
                    .slice(1, 7)
                    .map(img => img.src)
                    .filter(src => src && src.startsWith('http'));
            }''')

            browser.close()
            return {"context": texts, "yt": yt_link, "imgs": images}
    except Exception as e:
        print(f"Lỗi hệ thống: {e}")
        return {"context": "", "yt": "", "imgs": []}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    try:
        user_msg = request.json.get('msg', '')
        if not user_msg:
            return jsonify({"text": "Bạn chưa nhập câu hỏi."})

        # 1. Cào dữ liệu thô từ Google
        data = search_google_all_in_one(user_msg)
        
        # 2. Xử lý dữ liệu thô thành giao diện 'Thông minh' mà không cần API AI
        smart_text = clean_and_format(data['context'], user_msg)
        
        # 3. Tạo gợi ý thủ công dựa trên địa danh
        suggestions = [
            f"Đặc sản {user_msg}",
            f"Lịch trình 3 ngày tại {user_msg}"
        ]

        return jsonify({
            "text": smart_text,
            "images": data['imgs'],
            "youtube": data['yt'],
            "suggestions": suggestions
        })
    except Exception as e:
        return jsonify({"text": f"Có lỗi xảy ra: {str(e)}"})

if __name__ == '__main__':
    # Koyeb/Render dùng PORT từ environment
    port = int(os.environ.get("PORT", 8000))
    app.run(host='0.0.0.0', port=port)
