from flask import Flask, render_template, request, jsonify
from playwright.sync_api import sync_playwright
import os

app = Flask(__name__)

def search_comprehensive(query):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            page = browser.new_page()
            
            # 1. Tìm thông tin tổng hợp (Lịch sử, Văn hóa, Ẩm thực)
            search_url = f"https://www.google.com/search?q={query}+lịch+sử+văn+hoá+ẩm+thực+đặc+sản"
            page.goto(search_url, timeout=60000)
            
            # Lấy dữ liệu đoạn trích từ Google
            snippets = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('div.VwiC3b')).slice(0, 5).map(el => el.innerText).join(' | ');
            }''')
            
            # Lấy link YouTube đầu tiên
            yt = page.evaluate('() => document.querySelector("a[href*=\'youtube.com/watch\']")?.href || ""')
            
            # 2. Tìm hình ảnh
            page.goto(f"https://www.google.com/search?q={query}+vietnam+travel+photography&tbm=isch")
            imgs = page.evaluate('''() => {
                return Array.from(document.querySelectorAll('img')).slice(1, 6).map(i => i.src).filter(s => s.startsWith('http'));
            }''')
            
            browser.close()
            return {"context": snippets, "yt": yt, "imgs": imgs}
    except Exception as e:
        print(f"Lỗi Playwright: {e}")
        return None

@app.route('/')
def index(): return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    data = search_comprehensive(user_msg)
    
    if not data or not data['context']:
        return jsonify({"text": "AI đang khởi động trình duyệt trên server, vui lòng thử lại sau 30 giây!", "images": [], "youtube": "", "suggestions": []})

    parts = data['context'].split('|')
    
    # Xây dựng câu trả lời có cấu trúc
    html_res = f"""
    <div class='ai-response'>
        <h3 style='color:#0077b6; border-bottom:2px solid #00b4d8'>🌟 KHÁM PHÁ: {user_msg.upper()}</h3>
        <p><b>📜 Lịch sử & Con người:</b> {parts[0] if len(parts)>0 else 'Đang cập nhật...'}</p>
        <p><b>🏛️ Văn hóa & Cảnh quan:</b> {parts[1] if len(parts)>1 else 'Đang cập nhật...'}</p>
        <p><b>🍲 Ẩm thực đặc sắc:</b> {parts[2] if len(parts)>2 else 'Đang cập nhật...'}</p>
        <p><b>💡 Lời khuyên du lịch:</b> {parts[3] if len(parts)>3 else 'Hãy chuẩn bị trang phục phù hợp với thời tiết địa phương.'}</p>
    </div>
    """
    
    suggestions = [f"Món ăn phải thử ở {user_msg}?", f"Lịch trình 2 ngày 1 đêm tại {user_msg}"]
    
    return jsonify({
        "text": html_res,
        "images": data['imgs'],
        "youtube": data['yt'],
        "suggestions": suggestions
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
