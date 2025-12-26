from flask import Flask, render_template, request, jsonify
from duckduckgo_search import DDGS
import os

app = Flask(__name__)

def search_travel_data(query):
    try:
        results = {"text": "", "images": [], "videos": []}
        with DDGS() as ddgs:
            # 1. Lấy thông tin văn hóa/ẩm thực (Search)
            search_query = f"{query} lịch sử văn hóa ẩm thực đặc sản du lịch"
            main_search = list(ddgs.text(search_query, region='vn-vi', max_results=3))
            if main_search:
                content = ""
                for r in main_search:
                    content += f"🔹 {r['body']}\n\n"
                results["text"] = content
            
            # 2. Lấy hình ảnh thực tế
            image_search = list(ddgs.images(f"{query} du lịch cảnh đẹp", max_results=5))
            results["images"] = [img['image'] for img in image_search]
            
            # 3. Lấy link video thực tế (không chỉ là search link)
            video_search = list(ddgs.videos(f"du lịch {query} review", max_results=3))
            results["videos"] = [{"title": v['title'], "url": v['content']} for v in video_search]
            
        return results
    except Exception as e:
        print(f"Lỗi tìm kiếm: {e}")
        return None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat_endpoint():
    user_msg = request.json.get('msg', '')
    if not user_msg:
        return jsonify({"text": "Hãy nhập địa danh bạn muốn khám phá!"})

    data = search_travel_data(user_msg)
    
    if not data or not data['text']:
        return jsonify({
            "text": f"🤖 Rất tiếc, tôi không tìm thấy thông tin cụ thể về '{user_msg}'. Bạn có thể thử các địa danh nổi tiếng như Đà Lạt, Phú Quốc, Sa Pa...",
            "images": [],
            "videos": []
        })

    # Xây dựng nội dung phản hồi HTML đặc sắc
    video_html = "<h4>📺 Video trải nghiệm thực tế:</h4>"
    for v in data['videos']:
        video_html += f"<li><a href='{v['url']}' target='_blank' style='color:#00b4d8'><b>{v['title']}</b></a></li>"

    html_res = f"""
    <div style='line-height:1.6; font-family: Arial, sans-serif;'>
        <h2 style='color:#023e8a; border-bottom: 2px solid #00b4d8;'>🌟 KHÁM PHÁ {user_msg.upper()}</h2>
        <div style='background: #f8f9fa; padding: 10px; border-radius: 8px; margin-bottom: 10px;'>
            {data['text'].replace('\n', '<br>')}
        </div>
        {video_html}
    </div>
    """
    
    return jsonify({
        "text": html_res,
        "images": data['images'],
        "suggestions": [f"Đặc sản {user_msg}", f"Giá vé tham quan {user_msg}", "Lịch trình du lịch"]
    })

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
