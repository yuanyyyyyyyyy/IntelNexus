"""
IntelNexus GUI
=============
CustomTkinter-based GUI for IntelNexus.
"""

import os
import sys
import threading
from datetime import datetime

import customtkinter as ctk
from tkinter import filedialog

from llm import get_llm, refine_query, generate_summary
from llm_utils import get_model_choices
from web_search import get_web_results
from news_search import get_news_results
from darkweb_search import get_darkweb_results, is_available as darkweb_available
from scrape import scrape_multiple
from report_export import export_markdown


ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

SEARCH_MODES = {
    "web": "网页搜索",
    "news": "新闻资讯",
    "darkweb": "暗网搜索",
    "all": "全部来源"
}


class IntelNexusGUI(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("IntelNexus - 多源网络情报分析平台")
        self.geometry("1200x800")

        self.search_thread = None
        self.stop_search = False

        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.create_sidebar()
        self.create_main_area()

    def create_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(20, weight=1)

        title_label = ctk.CTkLabel(
            self.sidebar,
            text="IntelNexus",
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        subtitle = ctk.CTkLabel(
            self.sidebar,
            text="多源网络情报分析平台",
            font=ctk.CTkFont(size=12)
        )
        subtitle.grid(row=1, column=0, padx=20, pady=(0, 20))

        mode_label = ctk.CTkLabel(self.sidebar, text="搜索模式", font=ctk.CTkFont(size=14, weight="bold"))
        mode_label.grid(row=2, column=0, padx=20, pady=(10, 5))

        self.mode_var = ctk.StringVar(value="all")
        for i, (mode, label) in enumerate(SEARCH_MODES.items()):
            radio = ctk.CTkRadioButton(
                self.sidebar,
                text=label,
                variable=self.mode_var,
                value=mode
            )
            radio.grid(row=3 + i, column=0, padx=20, pady=5, sticky="w")

        model_label = ctk.CTkLabel(self.sidebar, text="AI模型", font=ctk.CTkFont(size=14, weight="bold"))
        model_label.grid(row=8, column=0, padx=20, pady=(20, 5))

        model_choices = get_model_choices()
        self.model_var = ctk.StringVar(value=model_choices[0] if model_choices else "qwen2.5:7b")
        self.model_combo = ctk.CTkComboBox(
            self.sidebar,
            values=model_choices,
            variable=self.model_var,
            state="readonly"
        )
        self.model_combo.grid(row=9, column=0, padx=20, pady=5, sticky="ew")

        threads_label = ctk.CTkLabel(self.sidebar, text="线程数", font=ctk.CTkFont(size=14, weight="bold"))
        threads_label.grid(row=10, column=0, padx=20, pady=(20, 5))

        self.threads_slider = ctk.CTkSlider(
            self.sidebar,
            from_=1,
            to=16,
            number_of_steps=15,
            command=self.update_threads_label
        )
        self.threads_slider.set(5)
        self.threads_slider.grid(row=11, column=0, padx=20, pady=5, sticky="ew")

        self.threads_label = ctk.CTkLabel(self.sidebar, text="5")
        self.threads_label.grid(row=12, column=0, padx=20, pady=(0, 10))

        about_label = ctk.CTkLabel(
            self.sidebar,
            text="© 2024 IntelNexus\nAI驱动的网络情报平台",
            font=ctk.CTkFont(size=10),
            text_color="gray"
        )
        about_label.grid(row=21, column=0, padx=20, pady=10)

    def update_threads_label(self, value):
        self.threads_label.configure(text=str(int(value)))

    def create_main_area(self):
        self.main_frame = ctk.CTkFrame(self, corner_radius=0)
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)

        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(2, weight=1)

        header = ctk.CTkLabel(
            self.main_frame,
            text="搜索查询",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        input_frame = ctk.CTkFrame(self.main_frame)
        input_frame.grid(row=1, column=0, sticky="ew", padx=20, pady=10)
        input_frame.grid_columnconfigure(0, weight=1)

        self.query_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="输入搜索内容...",
            height=40,
            font=ctk.CTkFont(size=14)
        )
        self.query_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))

        self.query_entry.bind("<Return>", lambda e: self.start_search())

        self.search_btn = ctk.CTkButton(
            input_frame,
            text="开始搜索",
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self.start_search
        )
        self.search_btn.grid(row=0, column=1)

        self.status_label = ctk.CTkLabel(
            self.main_frame,
            text="就绪",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.grid(row=2, column=0, padx=20, pady=(10, 5), sticky="w")

        self.progress_bar = ctk.CTkProgressBar(self.main_frame)
        self.progress_bar.grid(row=3, column=0, sticky="ew", padx=20, pady=5)
        self.progress_bar.set(0)

        result_label = ctk.CTkLabel(
            self.main_frame,
            text="分析报告",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        result_label.grid(row=4, column=0, padx=20, pady=(20, 10), sticky="w")

        self.result_text = ctk.CTkTextbox(self.main_frame, font=ctk.CTkFont(size=12))
        self.result_text.grid(row=5, column=0, sticky="nsew", padx=20, pady=10)

        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.grid(row=6, column=0, sticky="ew", padx=20, pady=10)

        self.save_btn = ctk.CTkButton(
            btn_frame,
            text="保存报告",
            command=self.save_report,
            state="disabled"
        )
        self.save_btn.pack(side="right")

    def start_search(self):
        query = self.query_entry.get().strip()
        if not query:
            return

        self.search_btn.configure(state="disabled", text="搜索中...")
        self.save_btn.configure(state="disabled")
        self.result_text.delete("1.0", "end")
        self.stop_search = False

        self.search_thread = threading.Thread(target=self.run_search, args=(query,))
        self.search_thread.start()

    def run_search(self, query):
        try:
            self.update_status("初始化LLM...", 0.05)
            model = self.model_var.get()
            threads = int(self.threads_slider.get())
            mode = self.mode_var.get()

            llm = get_llm(model)

            self.update_status("优化查询...", 0.1)
            query_variants = refine_query(llm, query)
            search_query = " | ".join(query_variants) if isinstance(query_variants, list) else query_variants

            self.update_status(f"搜索{SEARCH_MODES.get(mode, mode)}...", 0.2)
            results = []

            with threading.ThreadPoolExecutor(max_workers=threads) as executor:
                futures = []

                if mode in ["web", "all"]:
                    futures.append(executor.submit(get_web_results, search_query, threads, 20))

                if mode in ["news", "all"]:
                    futures.append(executor.submit(get_news_results, search_query, 15))

                if mode in ["darkweb", "all"] and darkweb_available():
                    futures.append(executor.submit(get_darkweb_results, search_query, threads))

                for f in futures:
                    try:
                        r = f.result()
                        if r:
                            results.extend(r)
                    except Exception as e:
                        print(f"Search error: {e}")

            self.update_status(f"找到 {len(results)} 条结果", 0.4)

            if not results:
                self.update_status("未找到结果", 0)
                self.search_complete()
                return

            self.update_status("抓取内容...", 0.6)
            scraped = scrape_multiple(results, max_workers=threads)

            self.update_status("生成报告...", 0.8)
            stream_handler = GUIStreamHandler(self.result_text)
            llm.callbacks = [stream_handler]

            summary = generate_summary(llm, query, scraped)

            self.update_status("完成", 1.0)
            self.search_complete()

        except Exception as e:
            self.update_status(f"错误: {str(e)}", 0)
            self.search_complete()

    def update_status(self, text, progress):
        self.after(0, lambda: self.status_label.configure(text=text))
        self.after(0, lambda: self.progress_bar.set(progress))

    def search_complete(self):
        self.after(0, lambda: self.search_btn.configure(state="normal", text="开始搜索"))
        self.after(0, lambda: self.save_btn.configure(state="normal"))

    def save_report(self):
        content = self.result_text.get("1.0", "end").strip()
        if not content:
            return

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"report_{timestamp}.md"

        filepath = filedialog.asksaveasfilename(
            defaultextension=".md",
            filetypes=[("Markdown", "*.md"), ("All files", "*.*")],
            initialfile=filename
        )

        if filepath:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                self.status_label.configure(text=f"已保存: {filepath}")
            except Exception as e:
                self.status_label.configure(text=f"保存失败: {str(e)}")


class GUIStreamHandler:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def on_llm_new_token(self, token, **kwargs):
        self.text_widget.insert("end", token)
        self.text_widget.see("end")


def run_gui():
    app = IntelNexusGUI()
    app.mainloop()


if __name__ == "__main__":
    run_gui()