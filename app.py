pip install streamlit

import streamlit as st
import asyncio
import google.generativeai as genai
from playwright.async_api import async_playwright

# --- CẤU HÌNH ---
st.set_page_config(page_title="AI Search Bot", page_icon="🌐")
st.title("🌐 AI Search Real-time Bot")

# Nhập API Key ngay trên giao diện cho tiện
api_key = st.sidebar.text_input("Nhập Gemini API Key:", type="password")

if api_key:
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')

# Khởi tạo lịch sử chat trong session của Streamlit
if "messages" not in st.session_state:
    st.session_state.messages = []

# Hàm cào Google (giống như các bước trước)
async def search_google_direct(query):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        try:
            await page.goto(f"https://www.google.com/search?q={query}", timeout=10000)
            await page.wait_for_selector('div.g', timeout=5000)
            results = await page.evaluate('''() => {
                let items = [];
                document.querySelectorAll('div.g').forEach((el, i) => {
                    if (i < 3) {
                        let t = el.querySelector('h3')?.innerText;
                        let s = el.querySelector('div.VwiC3b')?.innerText;
                        if (t && s) items.push(`${t}: ${s}`);
                    }
                });
                return items.join('\\n');
            }''')
        except:
            results = "Không lấy được dữ liệu mới nhất từ Google."
        await browser.close()
        return results
# Hiển thị lịch sử chat ra màn hình
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# Xử lý khi người dùng nhập câu hỏi
if prompt := st.chat_input("Hỏi tôi bất cứ thứ gì mới nhất..."):
    # 1. Hiển thị câu hỏi của user
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 2. Xử lý phản hồi của Bot
    with st.chat_message("assistant"):
        with st.status("🔍 Đang lên Google tìm kiếm..."):
            # Chạy hàm async trong Streamlit
            search_data = asyncio.run(search_google_direct(prompt))
            st.write("Đã tìm thấy dữ liệu. Đang tổng hợp...")

        # Tạo prompt gửi cho AI
        history_text = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages[-5:]])
        full_prompt = f"""
        Lịch sử: {history_text}
        Dữ liệu Google: {search_data}
        Câu hỏi: {prompt}
        Hãy trả lời ngắn gọn, có dẫn nguồn nếu có thể.
        """
        
        response =

model.generate_content(full_prompt)
        full_response = response.text
        st.markdown(full_response)

    # Lưu phản hồi vào lịch sử
    st.session_state.messages.append({"role": "assistant", "content": full_response})

from fpdf import FPDF

@app.route('/export-pdf', methods=['POST'])
def export_pdf():
    history = request.json.get('history', [])
    pdf = FPDF()
    pdf.add_page()
    
    # Bạn cần tải file font .ttf về và để vào thư mục fonts/
    # pdf.add_font('DejaVu', '', 'fonts/DejaVuSans.ttf', uni=True)
    pdf.set_font('Arial', 'B', 16)
    pdf.cell(0, 10, 'Lịch sử du lịch - Vietnam Travel AI', ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font('Arial', '', 12)
    for msg in history:
        role = "Bạn: " if msg['role'] == 'user' else "Bot: "
        pdf.multi_cell(0, 10, f"{role}{msg['content']}\n")
        pdf.ln(2)
        
    path = "history_travel.pdf"
    pdf.output(path)
    return send_file(path, as_attachment=True)

