from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os
import subprocess
import sys

app = Flask(__name__)

# Cơ chế tự cài đặt trình duyệt nếu bị thiếu trên môi trường Runtime của Render
def ensure_browser_installed():
    try:
        with sync_playwright() as p:
            # Thử khởi động thử, nếu lỗi nghĩa là chưa cài browser
            browser = p.chromium.launch(headless=True)
            browser.close()
    except Exception as e:
        print(f"--- Đang cài đặt bổ sung Chromium... ---")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium", "--with-deps"], check=True)

def search_comprehensive(query):
    # Đảm bảo browser luôn sẵn sàng trước khi search
    ensure_browser_installed()
    
    try:
        with sync_playwright() as p:
            # Cấu hình tối ưu cho RAM yếu (Render Free)
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox', 
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-setuid-sandbox',
                    '--no-first-run'
                ]
            )
            context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = context.new_page()
            
            # 1. Tìm thông tin tổng hợp (Lịch sử, Văn hóa, Ẩm thực)
            # Dùng site:vi.wikipedia.org hoặc google search trực tiếp
            search_url = f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực+đặc+sản+vietnam&hl=vi"
            page.goto(search_url, timeout=60000)
            
            # Lấy các đoạn mô tả từ Google Result
            snippets = page.evaluate('''() => {
                const elements = Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 4);
                return elements.map(el => el.innerText).join(' | ');
            }''')
            
            # 2. Tìm hình ảnh liên quan
            page.goto(f"https://www.google.com/search?q={query}+cảnh+đẹp+du+lịch+vietnam&tbm=isch&hl=vi")
            imgs = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img'))
                    .slice(2, 7)
                    .map(i => i.src)
                    .filter(s => s.startsWith('http'));
            }''')
            
            browser.close()
            
            # Tạo link YouTube tìm kiếm tự động
            yt_link = f"https://www.youtube.com/results?search_query=du+lich+{query.replace(' ', '+')}"
            
            return {"context": snippets, "imgs": imgs, "yt": yt_link}
            
    except Exception as e:
        print(f"Lỗi Playwright cụ thể: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    if not user_msg:
        return jsonify({"text": "Bạn muốn hỏi gì về địa điểm này?", "images": [], "youtube": "", "suggestions": []})

    data = search_comprehensive(user_msg)
    
    if not data or not data['context']:
        return jsonify({
            "text": "🤖 AI đang bận cập nhật dữ liệu hoặc trình duyệt đang khởi động lại trên Server. Vui lòng thử lại sau 10 giây!",
            "images": [],
            "youtube": "",
            "suggestions": ["Thử lại lần nữa", f"Thời tiết tại {user_msg}"]
        })

    # Phân tách nội dung thành các mục chuyên nghiệp
    parts = data['context'].split('|')
    history = parts[0] if len(parts) > 0 else "Đang cập nhật dữ liệu lịch sử..."
    culture = parts[1] if len(parts) > 1 else "Đang cập nhật nét đẹp văn hóa..."
    cuisine = parts[2] if len(parts) > 2 else "Đang cập nhật đặc sản vùng miền..."

    html_res = f"""
    <div style='line-height:1.6'>
        <h3 style='color:#0077b6; border-bottom:2px solid #00b4d8; padding-bottom:5px'>🌟 THÔNG TIN: {user_msg.upper()}</h3>
        <p><b>📜 Lịch sử & Phát triển:</b> {history}</p>
        <p><b>🏛️ Văn hóa & Con người:</b> {culture}</p>
        <p><b>🍲 Ẩm thực phải thử:</b> {cuisine}</p>
        <p><b>💡 Gợi ý du lịch:</b> Dựa trên dữ liệu, đây là thời điểm tuyệt vời để bạn ghé thăm và trải nghiệm không gian tại đây.</p>
    </div>
    """
    
    suggestions = [
        f"Món ăn đặc sản ở {user_msg}?",
        f"Lịch trình tour {user_msg} 1 ngày",
        f"Địa điểm chụp ảnh đẹp tại {user_msg}"
    ]
    
    return jsonify({
        "text": html_res,
        "images": data['imgs'],
        "youtube": data['yt'],
        "suggestions": suggestions
    })

if __name__ == '__main__':
    # Render yêu cầu bind vào port 10000 hoặc biến môi trường PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
