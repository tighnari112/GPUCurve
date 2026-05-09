import os
import time
import ctypes
import subprocess
import csv
import platform
import re
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, font
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib as mpl

# 检查并请求管理员权限
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


class GPUPerformanceTester:
    def __init__(self, root):
        self.root = root
        try:
            # 设置窗口标题
            self.root.title("GPU性能测试工具")
            
            # 固定窗口大小
            self.root.resizable(False, False)
            
            # 先初始化基本属性
            self.testing = False
            self.test_thread = None
            self.results = []
            self.detailed_data = []
            self.nvml_initialized = False
            
            # 默认配置
            self.config = {
                'furmark_path': "C:\\FurMark\\FurMark.exe",
                'output_dir': os.path.join(os.path.expanduser("~"), "Desktop"),
                'test_duration': 60,
                'cooldown_time': 60,
                'sample_interval': 0.5,
                'min_freq': 390,
                'max_freq': 420,
                'freq_step': 15,
                'font_family': "Microsoft YaHei",
                'font_size': 10,
                'furmark_width': 1920,
                'furmark_height': 1080,
                'furmark_msaa': 0,
                'nogui': True,
                'noscore': True,
                'matplotlib_font': "SimHei",
                'matplotlib_font_size': 10,
                'graphics_api': "OpenGL"  # 添加图形API选项
            }
            
            # 设置初始Matplotlib中文字体支持
            self.setup_matplotlib_fonts(self.config['matplotlib_font'])
            
            self.set_window_size()
            self.setup_ui()
            
            # 加载默认配置到UI
            self.load_default_config()
            
            # 初始化NVML（如果可用）
            if self.initialize_nvml():
                self.log("NVML初始化成功")
            else:
                self.log("警告: NVML初始化失败，部分功能受限")
            
            # 加载系统信息（在NVML初始化后调用）
            self.load_system_info()
            
            # 显示初始状态
            self.log("应用程序已启动")
            self.status_var.set("就绪")
            
        except Exception as e:
            messagebox.showerror("初始化错误", f"应用程序初始化失败: {str(e)}")
            self.root.destroy()
    
    def setup_matplotlib_fonts(self, font_name):
        """配置Matplotlib以支持中文字符显示"""
        try:
            # 设置中文字体
            plt.rcParams['font.sans-serif'] = [font_name, 'Microsoft YaHei', 'Arial Unicode MS', 'sans-serif']
            
            # 解决负号显示问题
            plt.rcParams['axes.unicode_minus'] = False
            
            # 设置默认字体大小
            plt.rcParams['font.size'] = self.config.get('matplotlib_font_size', 10)
            
            # 设置标题和标签字体
            plt.rcParams['axes.titlesize'] = 12
            plt.rcParams['axes.labelsize'] = 10
            
            # 设置图例字体
            plt.rcParams['legend.fontsize'] = 9
            
            # 设置刻度标签字体
            plt.rcParams['xtick.labelsize'] = 8
            plt.rcParams['ytick.labelsize'] = 8
            
            # 更新现有图表
            if hasattr(self, 'fig'):
                self.generate_chart()
        except Exception as e:
            print(f"设置Matplotlib字体失败: {e}")

    def set_window_size(self):
        """设置窗口大小为固定大小"""
        try:
            # 固定窗口大小
            width = 650
            height = 500
            
            # 居中窗口
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            
            self.root.geometry(f"{width}x{height}+{x}+{y}")
        except Exception as e:
            print(f"设置窗口大小失败: {e}")

    def setup_ui(self):
        try:
            # 创建菜单栏
            self.menu_bar = tk.Menu(self.root)
            self.root.config(menu=self.menu_bar)
            
            # 文件菜单
            file_menu = tk.Menu(self.menu_bar, tearoff=0)
            file_menu.add_command(label="保存配置", command=self.save_config)
            file_menu.add_command(label="加载配置", command=self.load_config)
            file_menu.add_separator()
            file_menu.add_command(label="退出", command=self.root.quit)
            self.menu_bar.add_cascade(label="文件", menu=file_menu)
            
            # 设置菜单
            settings_menu = tk.Menu(self.menu_bar, tearoff=0)
            settings_menu.add_command(label="字体设置", command=self.change_font)
            settings_menu.add_command(label="重置默认设置", command=self.reset_defaults)
            self.menu_bar.add_cascade(label="设置", menu=settings_menu)
            
            # 帮助菜单
            help_menu = tk.Menu(self.menu_bar, tearoff=0)
            help_menu.add_command(label="关于", command=self.show_about)
            self.menu_bar.add_cascade(label="帮助", menu=help_menu)
            
            # 创建主框架
            self.main_frame = ttk.Frame(self.root)
            self.main_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            # 创建选项卡
            self.notebook = ttk.Notebook(self.main_frame)
            self.notebook.pack(fill='both', expand=True)
            
            # 配置选项卡
            self.config_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.config_tab, text='测试配置')
            self.setup_config_tab()
            
            # 图表选项卡
            self.chart_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.chart_tab, text='结果图表')
            self.setup_chart_tab()
            
            # 日志选项卡
            self.log_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.log_tab, text='测试日志')
            self.setup_log_tab()

            # 系统信息选项卡
            self.system_info_tab = ttk.Frame(self.notebook)
            self.notebook.add(self.system_info_tab, text='系统信息')
            self.setup_system_info_tab()
            
            
        except Exception as e:
            messagebox.showerror("UI初始化错误", f"界面初始化失败: {str(e)}")

    def setup_config_tab(self):
        try:
            # 配置网格布局
            self.config_tab.columnconfigure(0, weight=1)
            self.config_tab.rowconfigure(0, weight=1)
            
            # 创建主框架（删除滚动条和右侧框架）
            main_frame = ttk.Frame(self.config_tab)
            main_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
        
            # 配置权重
            main_frame.columnconfigure(0, weight=1)
            main_frame.rowconfigure(0, weight=1)
            
            # 路径配置
            path_frame = ttk.LabelFrame(main_frame, text="路径设置")
            path_frame.pack(fill='x', padx=5, pady=5)
            
            # 使用pack布局替代grid，更适应小窗口
            path_row1 = ttk.Frame(path_frame)
            path_row1.pack(fill='x', pady=2)
            ttk.Label(path_row1, text="FurMark路径:").pack(side='left', padx=(0, 5))
            self.furmark_path_var = tk.StringVar()
            self.furmark_path_entry = ttk.Entry(path_row1, textvariable=self.furmark_path_var)
            self.furmark_path_entry.pack(side='left', fill='x', expand=True, padx=5)
            ttk.Button(path_row1, text="浏览...", command=self.browse_furmark).pack(side='left', padx=5)
            
            path_row2 = ttk.Frame(path_frame)
            path_row2.pack(fill='x', pady=2)
            ttk.Label(path_row2, text="输出目录:").pack(side='left', padx=(0, 5))
            self.output_dir_var = tk.StringVar()
            self.output_dir_entry = ttk.Entry(path_row2, textvariable=self.output_dir_var)
            self.output_dir_entry.pack(side='left', fill='x', expand=True, padx=5)
            ttk.Button(path_row2, text="浏览...", command=self.browse_output_dir).pack(side='left', padx=5)
        
            # 测试参数 - 使用pack布局
            param_frame = ttk.LabelFrame(main_frame, text="测试参数")
            param_frame.pack(fill='x', padx=5, pady=5)
            
            param_row = ttk.Frame(param_frame)
            param_row.pack(fill='x', pady=2)
            
            ttk.Label(param_row, text="测试持续时间 (秒):").pack(side='left', padx=(0, 5))
            self.test_duration_var = tk.IntVar()
            self.test_duration_entry = ttk.Entry(param_row, textvariable=self.test_duration_var, width=10)
            self.test_duration_entry.pack(side='left', padx=5)
            
            ttk.Label(param_row, text="冷却时间 (秒):").pack(side='left', padx=(10, 5))
            self.cooldown_time_var = tk.IntVar()
            self.cooldown_time_entry = ttk.Entry(param_row, textvariable=self.cooldown_time_var, width=10)
            self.cooldown_time_entry.pack(side='left', padx=5)
            
            ttk.Label(param_row, text="采样间隔 (秒):").pack(side='left', padx=(10, 5))
            self.sample_interval_var = tk.DoubleVar()
            self.sample_interval_entry = ttk.Entry(param_row, textvariable=self.sample_interval_var, width=10)
            self.sample_interval_entry.pack(side='left', padx=5)
        
            # 频率设置 - 使用pack布局
            freq_frame = ttk.LabelFrame(main_frame, text="频率设置 (MHz)")
            freq_frame.pack(fill='x', padx=5, pady=5)
            
            freq_row = ttk.Frame(freq_frame)
            freq_row.pack(fill='x', pady=2)
            
            ttk.Label(freq_row, text="起始频率:").pack(side='left', padx=(0, 5))
            self.min_freq_var = tk.IntVar()
            self.min_freq_entry = ttk.Entry(freq_row, textvariable=self.min_freq_var, width=10)
            self.min_freq_entry.pack(side='left', padx=5)
            
            ttk.Label(freq_row, text="结束频率:").pack(side='left', padx=(10, 5))
            self.max_freq_var = tk.IntVar()
            self.max_freq_entry = ttk.Entry(freq_row, textvariable=self.max_freq_var, width=10)
            self.max_freq_entry.pack(side='left', padx=5)
            
            ttk.Label(freq_row, text="步进值:").pack(side='left', padx=(10, 5))
            self.freq_step_var = tk.IntVar()
            self.freq_step_entry = ttk.Entry(freq_row, textvariable=self.freq_step_var, width=10)
            self.freq_step_entry.pack(side='left', padx=5)
        
            # FurMark参数 - 使用pack布局
            furmark_frame = ttk.LabelFrame(main_frame, text="FurMark设置")
            furmark_frame.pack(fill='x', padx=5, pady=5)
            
            furmark_row1 = ttk.Frame(furmark_frame)
            furmark_row1.pack(fill='x', pady=2)
            
            ttk.Label(furmark_row1, text="宽度:").pack(side='left', padx=(0, 5))
            self.furmark_width_var = tk.IntVar()
            self.furmark_width_entry = ttk.Entry(furmark_row1, textvariable=self.furmark_width_var, width=8)
            self.furmark_width_entry.pack(side='left', padx=5)
            
            ttk.Label(furmark_row1, text="高度:").pack(side='left', padx=(10, 5))
            self.furmark_height_var = tk.IntVar()
            self.furmark_height_entry = ttk.Entry(furmark_row1, textvariable=self.furmark_height_var, width=8)
            self.furmark_height_entry.pack(side='left', padx=5)
            
            ttk.Label(furmark_row1, text="MSAA级别:").pack(side='left', padx=(10, 5))
            self.furmark_msaa_var = tk.IntVar()
            self.furmark_msaa_entry = ttk.Entry(furmark_row1, textvariable=self.furmark_msaa_var, width=8)
            self.furmark_msaa_entry.pack(side='left', padx=5)
            
            furmark_row2 = ttk.Frame(furmark_frame)
            furmark_row2.pack(fill='x', pady=2)
            

            # 添加图形API选择
            ttk.Label(furmark_row2, text="图形API:").pack(side='left', padx=(0, 5))
            self.graphics_api_var = tk.StringVar()
            self.graphics_api_combo = ttk.Combobox(furmark_row2, textvariable=self.graphics_api_var, 
                                                 values=["OpenGL", "Vulkan"], width=8)
            self.graphics_api_combo.pack(side='left', padx=5)
            self.graphics_api_combo.current(0)  # 默认OpenGL
            
            # 高级选项使用Frame包裹
            advanced_frame = ttk.Frame(furmark_row2)
            advanced_frame.pack(side='left', padx=(10, 0))
            
            ttk.Label(advanced_frame, text="高级选项:").pack(side='left', padx=(0, 5))
            self.nogui_var = tk.BooleanVar()
            self.nogui_check = ttk.Checkbutton(advanced_frame, text="无GUI", variable=self.nogui_var)
            self.nogui_check.pack(side='left', padx=5)
            
            
            self.noscore_var = tk.BooleanVar()
            self.noscore_check = ttk.Checkbutton(advanced_frame, text="无分数框", variable=self.noscore_var)
            self.noscore_check.pack(side='left', padx=5)

            # 底部控制按钮 - 使用pack布局更适应小窗口
            button_frame = ttk.Frame(main_frame)
            button_frame.pack(fill='x', padx=5, pady=10)
            
            # 左侧按钮组
            left_btn_frame = ttk.Frame(button_frame)
            left_btn_frame.pack(side='left', fill='x', expand=True)
            
            self.start_btn = ttk.Button(left_btn_frame, text="开始测试", command=self.start_test)
            self.start_btn.pack(side='left', padx=5, pady=5)
        
            self.stop_btn = ttk.Button(left_btn_frame, text="停止测试", command=self.stop_test, state='disabled')
            self.stop_btn.pack(side='left', padx=5, pady=5)
        
            self.export_btn = ttk.Button(left_btn_frame, text="导出结果", command=self.export_results)
            self.export_btn.pack(side='left', padx=5, pady=5)
            
            # 右侧状态栏
            self.status_var = tk.StringVar(value="就绪")
            self.status_bar = ttk.Label(button_frame, textvariable=self.status_var, anchor='e')
            self.status_bar.pack(side='right', padx=(5, 0), pady=5, fill='x', expand=True)
        
        except Exception as e:
            messagebox.showerror("配置选项卡错误", f"配置选项卡初始化失败: {str(e)}")


    def setup_chart_tab(self):
        try:
            self.chart_tab.columnconfigure(0, weight=1)
            self.chart_tab.rowconfigure(0, weight=0)
            self.chart_tab.rowconfigure(1, weight=1)
            
            # 创建控制面板框架
            chart_control_frame = ttk.Frame(self.chart_tab)
            chart_control_frame.grid(row=0, column=0, sticky='ew', padx=10, pady=5)
            
            # 第一行控制元素
            row1_frame = ttk.Frame(chart_control_frame)
            row1_frame.pack(fill='x', pady=2)
            
            # X轴选择 - 添加电压选项
            ttk.Label(row1_frame, text="X轴:").pack(side='left', padx=(0, 5))
            self.x_var = tk.StringVar()
            x_options = ['频率', '功耗', 'FurMark2分数', '电压']  # 添加电压选项
            self.x_combo = ttk.Combobox(row1_frame, textvariable=self.x_var, 
                                        values=x_options, width=10, state="readonly")
            self.x_combo.pack(side='left', padx=5)
            self.x_combo.current(0)  # 默认选择频率
            
            # Y轴选择 - 添加电压选项
            ttk.Label(row1_frame, text="Y轴:").pack(side='left', padx=(10, 5))
            self.y_var = tk.StringVar()
            y_options = ['频率', '功耗', 'FurMark2分数', '电压']  # 添加电压选项
            self.y_combo = ttk.Combobox(row1_frame, textvariable=self.y_var, 
                                        values=y_options, width=10, state="readonly")
            self.y_combo.pack(side='left', padx=5)
            self.y_combo.current(1)  # 默认选择功耗
            
            # 第二行控制元素
            row2_frame = ttk.Frame(chart_control_frame)
            row2_frame.pack(fill='x', pady=2)
            
            # 图表类型选择
            ttk.Label(row2_frame, text="图表类型:").pack(side='left', padx=(0, 5))
            self.chart_type_var = tk.StringVar(value="折线图")
            chart_types = ["折线图", "散点图"]
            self.chart_type_combo = ttk.Combobox(row2_frame, textvariable=self.chart_type_var, 
                                               values=chart_types, width=8, state="readonly")
            self.chart_type_combo.pack(side='left', padx=5)
            
            # 添加趋势线选项
            self.trendline_var = tk.BooleanVar(value=True)
            self.trendline_check = ttk.Checkbutton(row2_frame, text="添加趋势线", 
                                                  variable=self.trendline_var)
            self.trendline_check.pack(side='left', padx=5)
            
            # 生成图表按钮
            ttk.Button(row2_frame, text="生成图表", command=self.generate_chart).pack(side='left', padx=5)
            
            # 图表框架
            self.chart_frame = ttk.Frame(self.chart_tab)
            self.chart_frame.grid(row=1, column=0, sticky='nsew', padx=10, pady=10)
            self.chart_frame.columnconfigure(0, weight=1)
            self.chart_frame.rowconfigure(0, weight=1)
            
            # 初始占位符 - 空白图表
            self.fig, self.ax = plt.subplots(figsize=(8, 6))
            self.ax.set_title("请选择数据并点击'生成图表'")
            self.ax.text(0.5, 0.5, "尚未生成图表\n请选择X轴和Y轴数据后点击'生成图表'按钮", 
                         ha='center', va='center', fontsize=12, color='gray')
            self.ax.axis('off')
            
            self.canvas = FigureCanvasTkAgg(self.fig, master=self.chart_frame)
            self.canvas.get_tk_widget().grid(row=0, column=0, sticky='nsew')
            
        except Exception as e:
            messagebox.showerror("图表选项卡错误", f"图表选项卡初始化失败: {str(e)}")

    def generate_chart(self):
        """根据用户选择的X轴和Y轴生成图表"""
        try:
            # 获取用户选择
            x_selection = self.x_var.get()
            y_selection = self.y_var.get()
            chart_type = self.chart_type_var.get()
            add_trendline = self.trendline_var.get()
            
            if not x_selection or not y_selection:
                messagebox.showwarning("警告", "请选择X轴和Y轴数据")
                return
                
            # 映射用户选择到数据列 - 添加电压映射
            column_map = {
                '频率': 'Avg_Actual_Freq(MHz)',
                '功耗': 'Avg_Power(W)',
                'FurMark2分数': 'Score',
                '电压': 'Avg_Voltage(V)'  # 添加电压映射
            }
            
            x_col = column_map.get(x_selection)
            y_col = column_map.get(y_selection)
            
            if not x_col or not y_col:
                messagebox.showerror("错误", "无效的轴选择")
                return
                
            # 创建DataFrame
            df = pd.DataFrame(self.results, columns=[
                'Target_Freq(MHz)', 
                'Avg_Actual_Freq(MHz)', 
                'Avg_Power(W)', 
                'Max_Power(W)', 
                'Avg_Temp(C)', 
                'Max_Temp(C)', 
                'Score',
                'Avg_Voltage(V)'  # 添加平均电压
            ])
            
            # 准备绘图
            self.fig.clf()
            self.ax = self.fig.add_subplot(111)
            
            # 根据图表类型绘图
            if chart_type == "折线图":
                self.ax.plot(df[x_col], df[y_col], 'b-o', linewidth=2, markersize=6, label='数据')
                if add_trendline:
                    # 添加多项式趋势线（2阶）
                    try:
                        z = np.polyfit(df[x_col], df[y_col], 2)
                        p = np.poly1d(z)
                        self.ax.plot(df[x_col], p(df[x_col]), 'r--', linewidth=1.5, label='趋势线')
                    except Exception as e:
                        self.log(f"添加趋势线失败: {str(e)}")
                    
            elif chart_type == "散点图":
                self.ax.scatter(df[x_col], df[y_col], s=50, c='blue', alpha=0.7, label='数据点')
                if add_trendline:
                    # 添加线性趋势线
                    try:
                        z = np.polyfit(df[x_col], df[y_col], 1)
                        p = np.poly1d(z)
                        self.ax.plot(df[x_col], p(df[x_col]), 'r--', linewidth=1.5, label='趋势线')
                    except Exception as e:
                        self.log(f"添加趋势线失败: {str(e)}")
            
            # 设置图表标题和标签
            self.ax.set_title(f"{y_selection} vs {x_selection}", fontsize=12)
            self.ax.set_xlabel(x_selection)
            self.ax.set_ylabel(y_selection)
            
            # 添加网格
            self.ax.grid(True, linestyle='--', alpha=0.7)
            
            # 如果添加了趋势线，显示图例
            if add_trendline:
                self.ax.legend(loc='best')
            
            # 自动调整布局
            self.fig.tight_layout()
            
            # 更新画布
            self.canvas.draw()
            
        except Exception as e:
            messagebox.showerror("图表生成错误", f"生成图表时出错: {str(e)}")
            # 恢复空白图表
            self.fig.clf()
            self.ax = self.fig.add_subplot(111)
            self.ax.set_title("图表生成失败")
            self.ax.text(0.5, 0.5, f"图表生成失败:\n{str(e)}", 
                         ha='center', va='center', fontsize=12, color='red')
            self.ax.axis('off')
            self.canvas.draw()

    def setup_log_tab(self):
        try:
            self.log_tab.columnconfigure(0, weight=1)
            self.log_tab.rowconfigure(0, weight=1)
            
            self.log_frame = ttk.Frame(self.log_tab)
            self.log_frame.grid(row=0, column=0, sticky='nsew', padx=10, pady=10)
            self.log_frame.columnconfigure(0, weight=1)
            self.log_frame.rowconfigure(0, weight=1)
            
            self.log_text = scrolledtext.ScrolledText(self.log_frame, wrap=tk.WORD)
            self.log_text.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)
            self.log_text.config(state='disabled')
            
            # 添加日志标题
            self.log("欢迎使用GPU性能测试工具")
            self.log("请配置测试参数后点击'开始测试'按钮")
            
            # 配置权重
            self.log_frame.rowconfigure(0, weight=1)
            self.log_frame.columnconfigure(0, weight=1)
        except Exception as e:
            messagebox.showerror("日志选项卡错误", f"日志选项卡初始化失败: {str(e)}")

    def setup_system_info_tab(self):
        """设置系统信息选项卡"""
        try:
            self.sys_frame = ttk.LabelFrame(self.system_info_tab, text="系统信息")
            self.sys_frame.pack(fill='both', expand=True, padx=10, pady=10)
            
            self.sys_info_text = scrolledtext.ScrolledText(self.sys_frame, wrap=tk.WORD)
            self.sys_info_text.pack(fill='both', expand=True, padx=5, pady=5)
            self.sys_info_text.config(state='disabled')
        except Exception as e:
            messagebox.showerror("系统信息选项卡错误", f"初始化失败: {str(e)}")

    def change_font(self):
        """更改应用程序字体和Matplotlib字体"""
        try:
            # 获取当前可用字体
            available_fonts = list(font.families())
            available_fonts.sort()
            
            # 创建字体选择对话框
            font_dialog = tk.Toplevel(self.root)
            font_dialog.title("字体设置")
            font_dialog.transient(self.root)
            font_dialog.grab_set()
            font_dialog.geometry("500x350")
            
            # 主应用字体设置
            ttk.Label(font_dialog, text="主应用字体:").grid(row=0, column=0, padx=10, pady=5, sticky='w')
            
            font_family_var = tk.StringVar(value=self.config['font_family'])
            font_family_combo = ttk.Combobox(font_dialog, textvariable=font_family_var, values=available_fonts, width=25)
            font_family_combo.grid(row=0, column=1, padx=10, pady=5, sticky='ew')
            
            ttk.Label(font_dialog, text="字体大小:").grid(row=0, column=2, padx=10, pady=5, sticky='w')
            
            font_size_var = tk.IntVar(value=self.config['font_size'])
            font_size_spin = ttk.Spinbox(font_dialog, textvariable=font_size_var, from_=8, to=20, width=5)
            font_size_spin.grid(row=0, column=3, padx=10, pady=5)
            
            # Matplotlib字体设置
            ttk.Label(font_dialog, text="图表字体:").grid(row=1, column=0, padx=10, pady=5, sticky='w')
            
            matplotlib_font_var = tk.StringVar(value=self.config['matplotlib_font'])
            matplotlib_font_combo = ttk.Combobox(font_dialog, textvariable=matplotlib_font_var, 
                                               values=available_fonts, width=25)
            matplotlib_font_combo.grid(row=1, column=1, padx=10, pady=5, sticky='ew')
            
            ttk.Label(font_dialog, text="图表字体大小:").grid(row=1, column=2, padx=10, pady=5, sticky='w')
            
            matplotlib_size_var = tk.IntVar(value=self.config['matplotlib_font_size'])
            matplotlib_size_spin = ttk.Spinbox(font_dialog, textvariable=matplotlib_size_var, from_=8, to=20, width=5)
            matplotlib_size_spin.grid(row=1, column=3, padx=10, pady=5)
            
            # 预览标签
            preview_label = ttk.Label(font_dialog, text="主应用字体预览: ABCDEFG abcdefg 1234567")
            preview_label.grid(row=2, column=0, columnspan=4, padx=10, pady=10)
            
            chart_preview_label = ttk.Label(font_dialog, text="图表字体预览: 中文标题 - 坐标轴标签 温度(℃) 频率(MHz)")
            chart_preview_label.grid(row=3, column=0, columnspan=4, padx=10, pady=10)
            
            def update_preview():
                try:
                    # 更新主应用字体预览
                    preview_font = font.Font(family=font_family_var.get(), size=font_size_var.get())
                    preview_label.config(font=preview_font)
                    
                    # 更新图表字体预览
                    chart_font = font.Font(family=matplotlib_font_var.get(), size=matplotlib_size_var.get())
                    chart_preview_label.config(font=chart_font)
                except:
                    pass
            
            font_family_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
            font_size_var.trace_add('write', lambda *args: update_preview())
            matplotlib_font_combo.bind('<<ComboboxSelected>>', lambda e: update_preview())
            matplotlib_size_var.trace_add('write', lambda *args: update_preview())
            update_preview()
            
            def apply_font():
                try:
                    # 保存主应用字体设置
                    self.config['font_family'] = font_family_var.get()
                    self.config['font_size'] = font_size_var.get()
                    self.apply_font_to_ui()
                    
                    # 保存Matplotlib字体设置
                    self.config['matplotlib_font'] = matplotlib_font_var.get()
                    self.config['matplotlib_font_size'] = matplotlib_size_var.get()
                    
                    # 应用Matplotlib字体设置
                    self.setup_matplotlib_fonts(matplotlib_font_var.get())
                    
                    font_dialog.destroy()
                except Exception as e:
                    messagebox.showerror("字体应用错误", f"应用字体设置失败: {str(e)}")
            
            ttk.Button(font_dialog, text="应用", command=apply_font).grid(row=4, column=0, columnspan=4, pady=10)
        except Exception as e:
            messagebox.showerror("字体设置错误", f"字体设置对话框初始化失败: {str(e)}")

    def apply_font_to_ui(self):
        """将字体设置应用到整个UI"""
        try:
            new_font = font.Font(family=self.config['font_family'], size=self.config['font_size'])
            
            # 应用字体到所有控件
            for widget in self.root.winfo_children():
                self.apply_font_recursive(widget, new_font)
        except Exception as e:
            print(f"应用字体失败: {e}")

    def save_config(self):
        """保存配置到文件"""
        try:
            file_path = filedialog.asksaveasfilename(
                title="保存配置",
                defaultextension=".cfg",
                filetypes=[("配置文件", "*.cfg"), ("所有文件", "*.*")]
            )
            
            if not file_path:
                return
            
            config = self.get_config()
            with open(file_path, 'w') as f:
                for key, value in config.items():
                    f.write(f"{key}={value}\n")
            messagebox.showinfo("成功", "配置已保存")
        except Exception as e:
            messagebox.showerror("错误", f"保存配置失败: {str(e)}")

    def load_config(self):
        """从文件加载配置"""
        try:
            file_path = filedialog.askopenfilename(
                title="加载配置",
                filetypes=[("配置文件", "*.cfg"), ("所有文件", "*.*")]
            )
            
            if not file_path:
                return
            
            config = {}
            with open(file_path, 'r') as f:
                for line in f:
                    key, value = line.strip().split('=', 1)
                    config[key] = value
            
            # 更新UI
            self.furmark_path_var.set(config.get('furmark_path', self.config['furmark_path']))
            self.output_dir_var.set(config.get('output_dir', self.config['output_dir']))
            self.test_duration_var.set(int(config.get('test_duration', self.config['test_duration'])))
            self.cooldown_time_var.set(int(config.get('cooldown_time', self.config['cooldown_time'])))
            self.sample_interval_var.set(float(config.get('sample_interval', self.config['sample_interval'])))
            self.min_freq_var.set(int(config.get('min_freq', self.config['min_freq'])))
            self.max_freq_var.set(int(config.get('max_freq', self.config['max_freq'])))
            self.freq_step_var.set(int(config.get('freq_step', self.config['freq_step'])))
            
            # FurMark设置
            self.furmark_width_var.set(int(config.get('furmark_width', self.config['furmark_width'])))
            self.furmark_height_var.set(int(config.get('furmark_height', self.config['furmark_height'])))
            self.furmark_msaa_var.set(int(config.get('furmark_msaa', self.config['furmark_msaa'])))
            self.nogui_var.set(config.get('nogui', 'True') == 'True')
            self.noscore_var.set(config.get('noscore', 'True') == 'True')
            self.graphics_api_var.set(config.get('graphics_api', self.config['graphics_api']))
            
            # 更新字体配置
            if 'font_family' in config and 'font_size' in config:
                self.config['font_family'] = config['font_family']
                self.config['font_size'] = int(config['font_size'])
                self.apply_font_to_ui()
            
            # 更新Matplotlib字体配置
            if 'matplotlib_font' in config:
                self.config['matplotlib_font'] = config['matplotlib_font']
            
            if 'matplotlib_font_size' in config:
                self.config['matplotlib_font_size'] = int(config['matplotlib_font_size'])
            
            # 应用Matplotlib字体设置
            self.setup_matplotlib_fonts(self.config['matplotlib_font'])
            
            messagebox.showinfo("成功", "配置已加载")
        except Exception as e:
            messagebox.showerror("错误", f"加载配置失败: {str(e)}")

    def reset_defaults(self):
        """重置为默认设置"""
        try:
            self.load_default_config()
            messagebox.showinfo("成功", "已恢复默认设置")
        except Exception as e:
            messagebox.showerror("错误", f"重置默认设置失败: {str(e)}")

    def apply_font_recursive(self, widget, new_font):
        """递归应用字体设置"""
        try:
            if isinstance(widget, (ttk.Entry, ttk.Combobox, ttk.Button, ttk.Label, ttk.Checkbutton)):
                widget.configure(font=new_font)
            elif isinstance(widget, scrolledtext.ScrolledText):
                widget.configure(font=new_font)
        except:
            pass
        
        # 递归处理子控件
        for child in widget.winfo_children():
            self.apply_font_recursive(child, new_font)
    
    def show_about(self):
        """显示关于对话框"""
        about_text = (
            "GPU性能测试工具 \n"
            "版本: 4.0\n"
            "开发日期: 2024-04-15\n\n"
            "功能:\n"
            "- 自动化GPU频率和功耗测试\n"
            "- 支持FurMark2基准测试\n"
            "- 支持OpenGL和Vulkan API\n"
            "- 实时监控和图表展示\n"
            "- 自定义字体和布局\n"
            "- 优化的FurMark2命令行控制\n\n"
            "注意: 运行本程序需要管理员权限"
        )
        messagebox.showinfo("关于", about_text)

    def log(self, message):
        """在日志区域添加消息"""
        try:
            self.log_text.config(state='normal')
            self.log_text.insert(tk.END, f"[{time.strftime('%H:%M:%S')}] {message}\n")
            self.log_text.see(tk.END)
            self.log_text.config(state='disabled')
        except:
            pass

    def browse_furmark(self):
        """浏览选择FurMark程序路径"""
        try:
            file_path = filedialog.askopenfilename(
                title="选择FurMark程序",
                filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")]
            )
            if file_path:
                self.furmark_path_var.set(file_path)
        except Exception as e:
            messagebox.showerror("错误", f"选择FurMark路径失败: {str(e)}")

    def browse_output_dir(self):
        """浏览选择输出目录"""
        try:
            dir_path = filedialog.askdirectory(title="选择输出目录")
            if dir_path:
                self.output_dir_var.set(dir_path)
        except Exception as e:
            messagebox.showerror("错误", f"选择输出目录失败: {str(e)}")

    def load_default_config(self):
        """加载默认配置到UI"""
        try:
            self.furmark_path_var.set(self.config['furmark_path'])
            self.output_dir_var.set(self.config['output_dir'])
            self.test_duration_var.set(self.config['test_duration'])
            self.cooldown_time_var.set(self.config['cooldown_time'])
            self.sample_interval_var.set(self.config['sample_interval'])
            self.min_freq_var.set(self.config['min_freq'])
            self.max_freq_var.set(self.config['max_freq'])
            self.freq_step_var.set(self.config['freq_step'])
            
            # FurMark设置
            self.furmark_width_var.set(self.config['furmark_width'])
            self.furmark_height_var.set(self.config['furmark_height'])
            self.furmark_msaa_var.set(self.config['furmark_msaa'])
            self.graphics_api_var.set(self.config['graphics_api'])
            self.nogui_var.set(self.config['nogui'])
            self.noscore_var.set(self.config['noscore'])
            
            # 应用默认字体
            self.apply_font_to_ui()
            
            # 应用Matplotlib字体
            self.setup_matplotlib_fonts(self.config['matplotlib_font'])
        except Exception as e:
            messagebox.showerror("配置错误", f"加载默认配置失败: {str(e)}")

    def load_system_info(self):
        """加载系统信息"""
        try:
            self.sys_info_text.config(state='normal')
            self.sys_info_text.delete(1.0, tk.END)
            
            # 获取系统信息
            self.sys_info_text.insert(tk.END, "=== 系统信息 ===\n")
            self.sys_info_text.insert(tk.END, f"操作系统: {platform.system()} {platform.release()}\n")
            self.sys_info_text.insert(tk.END, f"系统版本: {platform.version()}\n")
            self.sys_info_text.insert(tk.END, f"处理器: {platform.processor()}\n")
            
            # 获取GPU信息
            if self.nvml_initialized:
                from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetName, nvmlSystemGetDriverVersion, nvmlDeviceGetMemoryInfo
                handle = nvmlDeviceGetHandleByIndex(0)
                gpu_name = nvmlDeviceGetName(handle)
                driver_version = nvmlSystemGetDriverVersion()
                mem_info = nvmlDeviceGetMemoryInfo(handle)
                
                self.sys_info_text.insert(tk.END, "=== GPU信息 ===\n")
                self.sys_info_text.insert(tk.END, f"GPU名称: {gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else gpu_name}\n")
                self.sys_info_text.insert(tk.END, f"驱动版本: {driver_version.decode('utf-8') if isinstance(driver_version, bytes) else driver_version}\n")
                self.sys_info_text.insert(tk.END, f"显存总量: {mem_info.total / 1024**2:.0f} MB\n")
            else:
                self.sys_info_text.insert(tk.END, "=== GPU信息 ===\n")
                self.sys_info_text.insert(tk.END, "无法获取GPU信息 (NVML未初始化)\n")
                
        except Exception as e:
            self.sys_info_text.insert(tk.END, f"获取系统信息失败: {str(e)}\n")
        finally:
            self.sys_info_text.config(state='disabled')

    def get_config(self):
        """从UI获取配置"""
        return {
            'furmark_path': self.furmark_path_var.get(),
            'output_dir': self.output_dir_var.get(),
            'test_duration': self.test_duration_var.get(),
            'cooldown_time': self.cooldown_time_var.get(),
            'sample_interval': self.sample_interval_var.get(),
            'min_freq': self.min_freq_var.get(),
            'max_freq': self.max_freq_var.get(),
            'freq_step': self.freq_step_var.get(),
            'font_family': self.config['font_family'],
            'font_size': self.config['font_size'],
            'furmark_width': self.furmark_width_var.get(),
            'furmark_height': self.furmark_height_var.get(),
            'furmark_msaa': self.furmark_msaa_var.get(),
            'graphics_api': self.graphics_api_var.get(),
            'nogui': self.nogui_var.get(),
            'noscore': self.noscore_var.get(),
            'matplotlib_font': self.config['matplotlib_font'],
            'matplotlib_font_size': self.config['matplotlib_font_size']
        }

    def start_test(self):
        """开始测试"""
        if self.testing:
            return
            
        try:
            config = self.get_config()
            
            # 验证配置
            if not os.path.exists(config['furmark_path']):
                messagebox.showerror("错误", "FurMark路径无效，请选择正确的程序路径")
                return
            
            if not config['output_dir']:
                messagebox.showerror("错误", "请选择输出目录")
                return
            
            if config['min_freq'] >= config['max_freq']:
                messagebox.showerror("错误", "起始频率必须小于结束频率")
                return
            
            if config['freq_step'] <= 0:
                messagebox.showerror("错误", "步进值必须大于0")
                return
            
            frequency_range = config['max_freq'] - config['min_freq']
            if frequency_range % config['freq_step'] != 0:
                error_msg = f"频率范围({frequency_range}MHz)不能被步进值({config['freq_step']}MHz)整除"
                messagebox.showerror("配置错误", error_msg)
                return
            
            # 创建输出目录
            try:
                os.makedirs(config['output_dir'], exist_ok=True)
            except Exception as e:
                messagebox.showerror("错误", f"无法创建输出目录: {str(e)}")
                return
            
            # 更新状态
            self.testing = True
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            self.status_var.set("测试运行中...")
            
            # 清空旧结果
            self.results = []
            self.detailed_data = []
            self.log_text.config(state='normal')
            self.log_text.delete(1.0, tk.END)
            self.log_text.config(state='disabled')
            self.log("开始GPU性能测试")
            
            # 在新线程中运行测试
            self.test_thread = threading.Thread(target=self.run_test, args=(config,))
            self.test_thread.daemon = True
            self.test_thread.start()
        except Exception as e:
            messagebox.showerror("测试启动错误", f"启动测试失败: {str(e)}")

    def stop_test(self):
        """停止测试"""
        if self.testing:
            self.testing = False
            self.log("测试已停止")
            self.status_var.set("测试已停止")

    def run_test(self, config):
        """运行测试的线程函数"""
        try:
            # 准备测试频率列表
            test_frequencies = list(range(config['min_freq'], config['max_freq'] + 1, config['freq_step']))
            
            self.log(f"测试范围: {config['min_freq']}-{config['max_freq']}MHz, 步进: {config['freq_step']}MHz")
            self.log(f"每次测试持续时间: {config['test_duration']}秒")
            self.log(f"图形API: {config['graphics_api']}")
            self.log(f"共 {len(test_frequencies)} 个频率点")
            
            # 主测试循环
            for i, freq in enumerate(test_frequencies):
                if not self.testing:
                    break
                    
                self.log(f"\n=== 测试 {i+1}/{len(test_frequencies)}: {freq} MHz ===")
                self.status_var.set(f"测试中: {freq}MHz ({i+1}/{len(test_frequencies)})")
                
                # 设置目标频率
                if not self.set_gpu_frequency(freq):
                    self.log(f"无法设置频率 {freq}MHz，跳过")
                    continue
                
                # 等待频率稳定
                time.sleep(2)
                
                # 运行FurMark测试
                furmark_process = self.run_furmark_test(config)
                if not furmark_process:
                    continue
                
                # 监控功耗、频率、温度和电压
                timestamps, power_readings, freq_readings, temp_readings = self.monitor_power_during_test(
                    config['test_duration'], config['sample_interval'],config)
                
                # 等待FurMark完成
                try:
                    furmark_process.wait(timeout=config['test_duration'] + 30)
                except subprocess.TimeoutExpired:
                    self.log("FurMark测试超时，强制终止")
                    furmark_process.terminate()
                
                # 获取FurMark分数
                score = self.parse_furmark_score(config['furmark_path'])
                
                # 计算平均值
                avg_power = np.mean(power_readings) if power_readings else 0
                max_power = np.max(power_readings) if power_readings else 0
                avg_freq = np.mean(freq_readings) if freq_readings else 0
                avg_temp = np.mean(temp_readings) if temp_readings else 0
                max_temp = np.max(temp_readings) if temp_readings else 0
                avg_voltage = self.get_gpu_voltage(config)
                
                # 保存结果 - 添加电压数据
                self.results.append([
                    freq,
                    avg_freq,
                    avg_power,
                    max_power,
                    avg_temp,
                    max_temp,
                    score,
                    avg_voltage  # 平均电压
                ])
                
                # 保存详细数据 - 添加电压数据
                self.detailed_data.append({
                    'freq': freq,
                    'timestamps': timestamps,
                    'power': power_readings,
                    'actual_freq': freq_readings,
                    'temperature': temp_readings,
                })
                
                # 打印当前结果
                self.log(f"实际平均频率: {avg_freq:.0f}MHz")
                self.log(f"平均功耗: {avg_power:.1f}W | 最大功耗: {max_power:.1f}W")
                self.log(f"平均温度: {avg_temp:.1f}°C | 最高温度: {max_temp:.1f}°C")
                self.log(f"平均电压: {avg_voltage:.3f}V")
                self.log(f"FurMark2分数: {score:.0f}")
                
                # 重置频率并冷却
                self.reset_gpu_frequency()
                self.log(f"冷却中，等待 {config['cooldown_time']} 秒...")
                
                # 冷却倒计时
                for remaining in range(config['cooldown_time'], 0, -1):
                    if not self.testing:
                        break
                    self.status_var.set(f"冷却中: {remaining}秒...")
                    time.sleep(1)
                
                if not self.testing:
                    break
            
            # 保存汇总结果
            if self.results:
                self.save_summary_to_excel(config['output_dir'])
                # 保存所有详细数据到单个文件
                self.save_all_detailed_data(config['output_dir'])
                self.log("\n所有测试完成! 结果已保存")
                self.status_var.set("测试完成")
            else:
                self.log("\n测试已取消或未完成")
                self.status_var.set("测试已取消")
            
        except Exception as e:
            self.log(f"测试过程中出错: {str(e)}")
            self.status_var.set("测试出错")
            import traceback
            self.log(f"错误详情:\n{traceback.format_exc()}")
        finally:
            # 更新UI状态
            self.testing = False
            self.root.after(0, self.update_ui_after_test)

    def update_ui_after_test(self):
        """测试结束后更新UI状态"""
        try:
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
        except:
            pass

    def set_gpu_frequency(self, freq_mhz):
        """设置GPU核心频率"""
        if not self.nvml_initialized:
            self.log("警告: NVML未初始化，无法设置频率")
            return False
            
        try:
            from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceSetGpuLockedClocks
            handle = nvmlDeviceGetHandleByIndex(0)
            nvmlDeviceSetGpuLockedClocks(handle, freq_mhz, freq_mhz)
            self.log(f"频率设置为: {freq_mhz}MHz")
            return True
        except Exception as err:
            self.log(f"设置频率{freq_mhz}MHz失败: {err}")
            return False

    def reset_gpu_frequency(self):
        """重置GPU频率到默认"""
        if not self.nvml_initialized:
            return
            
        try:
            from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceResetGpuLockedClocks
            handle = nvmlDeviceGetHandleByIndex(0)
            nvmlDeviceResetGpuLockedClocks(handle)
            self.log("已重置GPU频率")
        except Exception as err:
            self.log(f"重置频率失败: {err}")

    def get_actual_gpu_frequency(self):
        """获取实际GPU频率"""
        if not self.nvml_initialized:
            return 0
            
        try:
            from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetClockInfo, NVML_CLOCK_GRAPHICS
            handle = nvmlDeviceGetHandleByIndex(0)
            return nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)
        except:
            return 0

    def get_gpu_temperature(self):
        """获取GPU温度"""
        if not self.nvml_initialized:
            return 0
            
        try:
            from pynvml import nvmlDeviceGetHandleByIndex, nvmlDeviceGetTemperature, NVML_TEMPERATURE_GPU
            handle = nvmlDeviceGetHandleByIndex(0)
            return nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
        except:
            return 0

    def get_total_gpu_power(self):
        """获取整卡功耗（使用nvidia-smi）"""
        try:
            startupinfo = None
            if os.name == 'nt':
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # 隐藏窗口
            
            result = subprocess.run(
                ['nvidia-smi', '--query-gpu=power.draw', '--format=csv,noheader,nounits'],
                capture_output=True, 
                text=True, 
                check=True,
                startupinfo=startupinfo  # 添加此参数
            )
            power_str = result.stdout.strip().replace(' W', '')
            return float(power_str)
        except (subprocess.CalledProcessError, ValueError) as err:
            self.log(f"获取整卡功耗失败: {err}")
            return 0.0

    def get_gpu_voltage(self, config):
        """在测试完成后获取GPU核心电压数据"""
        try:
            # 获取exports文件夹路径
            furmark_dir = os.path.dirname(config['furmark_path'])
            exports_dir = os.path.join(furmark_dir, "exports")
            
            if not os.path.exists(exports_dir):
                self.log(f"exports文件夹未找到: {exports_dir}")
                return 0.0
            
            # 获取所有CSV文件并按修改时间排序
            csv_files = [f for f in os.listdir(exports_dir) if f.endswith('.csv')]
            if not csv_files:
                self.log("exports文件夹中没有CSV文件")
                return 0.0
                
            # 按修改时间排序，获取最新的文件
            csv_files.sort(key=lambda f: os.path.getmtime(os.path.join(exports_dir, f)), reverse=True)
            latest_file = os.path.join(exports_dir, csv_files[0])
            self.log(f"使用最新导出的CSV文件: {latest_file}")
            
            # 读取CSV文件并计算电压平均值
            voltage_values = []
            with open(latest_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f)
                
                # 跳过标题行
                next(reader, None)
                
                # 读取所有数据行
                for row in reader:
                    if len(row) >= 16:  # 确保有足够的列
                        try:
                            # P列是第16列（索引15）
                            voltage_value = float(row[15])
                            voltage_values.append(voltage_value)
                        except (ValueError, IndexError):
                            pass
            
            # 计算电压平均值
            avg_voltage = np.mean(voltage_values) if voltage_values else 0.0
            
            return avg_voltage
                
        except Exception as err:
            self.log(f"解析电压文件失败: {err}")
            import traceback
            self.log(f"错误详情:\n{traceback.format_exc()}")
            return 0.0

    def filter_outliers(self, data):
        """使用IQR方法过滤异常值"""
        if not data or len(data) < 5:
            return data
        
        try:
            # 计算四分位数
            q1 = np.percentile(data, 25)
            q3 = np.percentile(data, 75)
            iqr = q3 - q1
            
            # 定义异常值范围
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            # 过滤异常值
            filtered = [x for x in data if lower_bound <= x <= upper_bound]
            return filtered
        except:
            return data

    def monitor_power_during_test(self, duration, interval,config):
        """在测试过程中监控功耗、频率、温度和电压"""
        timestamps = []
        power_readings = []
        freq_readings = []
        temp_readings = []
        voltage_readings = []  # 添加电压监控
        
        start_time = time.time()
        elapsed = 0
        
        while elapsed < duration and self.testing:
            try:
                # 获取当前状态
                current_time = time.time() - start_time
                power = self.get_total_gpu_power()
                freq = self.get_actual_gpu_frequency()
                temp = self.get_gpu_temperature()
                
                # 记录数据
                timestamps.append(current_time)
                power_readings.append(power)
                freq_readings.append(freq)
                temp_readings.append(temp)
                
                # 显示实时信息 - 添加电压显示
                status = f"测试中: {elapsed:.1f}/{duration}秒 | 功耗: {power:.1f}W | 频率: {freq}MHz | 温度: {temp}°C |"
                self.status_var.set(status)
                
                # 等待下一次采样
                time.sleep(interval)
                elapsed = time.time() - start_time
            except Exception as err:
                self.log(f"监控出错: {err}")
                break
        
        # 过滤异常值 - 使用IQR方法
        filtered_voltage = self.filter_outliers(voltage_readings)
        if filtered_voltage:
            voltage_readings = filtered_voltage
            self.log(f"电压数据过滤: 原始{len(voltage_readings)}点 → 过滤后{len(filtered_voltage)}点")
        
        return timestamps, power_readings, freq_readings, temp_readings

    def run_furmark_test(self, config):
        """运行FurMark2测试"""
        try:
            # 获取FurMark目录和完整路径
            furmark_dir = os.path.dirname(config['furmark_path'])
            furmark_exe = os.path.basename(config['furmark_path'])
            
            # 验证FurMark可执行文件是否存在
            if not os.path.isfile(config['furmark_path']):
                self.log(f"错误：FurMark可执行文件不存在: {config['furmark_path']}")
                return None
                
            # 构建命令 - 使用完整路径
            cmd = [config['furmark_path']]
            
            # 添加图形API参数
            cmd += ["--demo", "furmark-vk" if config['graphics_api'] == "Vulkan" else "furmark-gl"]
            
            # 添加其他参数
            params = [
                ("--width", config['furmark_width']),
                ("--height", config['furmark_height']),
                ("--msaa", config['furmark_msaa']),
                ("--max-time", config['test_duration'])
            ]
            
            for param, value in params:
                cmd.extend([param, str(value)])
            
            # 添加开关参数
            cmd.append("--benchmark")
            
            if config['nogui']:
                cmd.append("--no-osi")
            if config['noscore']:
                cmd.append("--no-score-box")

            cmd.append("--log-gpu-data")

            cmd.append("--hw-polling-interval 50")
            
            # 详细日志
            self.log(f"启动FurMark测试:")
            self.log(f"  工作目录: {furmark_dir}")
            self.log(f"  完整命令: {' '.join(cmd)}")
            
            # 在Windows上使用CREATE_NO_WINDOW标志
            creation_flags = 0
            if os.name == 'nt':
                creation_flags = subprocess.CREATE_NO_WINDOW
                
            # 使用Shell执行作为备选方案
            try:
                # 首选方法：直接执行 (已应用CREATE_NO_WINDOW)
                process = subprocess.Popen(
                    cmd,
                    cwd=furmark_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=creation_flags
                )
                return process
            except FileNotFoundError:
                # 备选方法：通过Shell执行 - 这里添加CREATE_NO_WINDOW
                self.log("尝试通过Shell执行...")
                process = subprocess.Popen(
                    ' '.join(cmd),
                    cwd=furmark_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    shell=True,
                    creationflags=creation_flags  # 添加此行
                )
                return process
                
        except Exception as err:
            self.log(f"启动FurMark失败: {str(err)}")
            # 添加详细错误信息
            import traceback
            self.log(f"错误详情:\n{traceback.format_exc()}")
            return None

    def parse_furmark_score(self, furmark_path):
        """解析FurMark2测试分数 - 从_scores.csv文件读取"""
        try:
            # 分数文件路径
            score_file = os.path.join(os.path.dirname(furmark_path), "_scores.csv")
            
            if not os.path.exists(score_file):
                self.log(f"分数文件未找到: {score_file}")
                return 0
                
            with open(score_file, 'r', newline='', encoding='utf-8') as f:
                # 使用CSV读取器解析文件
                reader = csv.reader(f)
                
                # 跳过标题行（第1行）
                next(reader, None)  # 跳过第一行
                
                # 读取所有数据行
                rows = list(reader)
                
                if not rows:
                    self.log("分数文件为空")
                    return 0
                    
                # 获取最新测试结果（最后一行）
                last_row = rows[-1]
                
                # 确保行有足够的列数（M列是第13列，索引12）
                if len(last_row) < 13:
                    self.log(f"行数据不足: 只有{len(last_row)}列，需要至少13列")
                    return 0
                    
                # 获取M列的值（索引12）
                score_value = last_row[12]
                
                # 尝试转换为浮点数或整数
                try:
                    # 先尝试浮点数转换（可能有小数）
                    score = float(score_value)
                    # 如果是整数，转换为整数类型
                    if score.is_integer():
                        return int(score)
                    return score
                except ValueError:
                    # 如果无法转换为数字，尝试提取数字部分
                    match = re.search(r"(\d+\.?\d*)", score_value)
                    if match:
                        try:
                            return float(match.group(1))
                        except:
                            pass
                    
                    self.log(f"无法解析分数值: '{score_value}'")
                    return 0
                    
        except Exception as err:
            self.log(f"解析FurMark2分数失败: {err}")
            import traceback
            self.log(f"错误详情:\n{traceback.format_exc()}")
            return 0

    def save_all_detailed_data(self, output_dir):
        """保存所有详细数据到单个CSV文件"""
        filename = os.path.join(output_dir, "all_frequencies_detail.csv")
        try:
            with open(filename, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Timestamp(s)', 'Power(W)', 'Actual_Freq(MHz)', 
                                'Temperature(C)', 'Target_Freq(MHz)'])
                
                for data in self.detailed_data:
                    freq = data['freq']
                    for i in range(len(data['timestamps'])):
                        writer.writerow([
                            data['timestamps'][i],
                            data['power'][i],
                            data['actual_freq'][i],
                            data['temperature'][i],
                            freq
                        ])
            
            self.log(f"所有详细数据已保存到: {filename}")
            return filename
        except Exception as err:
            self.log(f"保存详细数据失败: {err}")
            return None

    def save_summary_to_excel(self, output_dir):
        """保存汇总结果到Excel"""
        try:
            # 创建DataFrame - 添加电压列
            df = pd.DataFrame(self.results, columns=[
                'Target_Freq(MHz)', 
                'Avg_Actual_Freq(MHz)', 
                'Avg_Power(W)', 
                'Max_Power(W)', 
                'Avg_Temp(C)', 
                'Max_Temp(C)', 
                'Score',
                'Avg_Voltage(V)'  # 添加平均电压
            ])
            
            # 保存到Excel
            excel_path = os.path.join(output_dir, "gpu_performance_summary.xlsx")
            try:
                df.to_excel(excel_path, index=False, engine='openpyxl')
                self.log(f"\n汇总结果已保存到: {excel_path}")
            except ImportError:
                # 如果缺少openpyxl，使用csv格式
                self.log("警告: 缺少openpyxl库，无法保存为Excel格式，将使用CSV格式")
                csv_path = os.path.join(output_dir, "gpu_performance_summary.csv")
                df.to_csv(csv_path, index=False)
                self.log(f"汇总结果已保存为CSV: {csv_path}")
            
            # 创建图表
            self.create_performance_charts(df, output_dir)
            
            return excel_path
        except Exception as err:
            self.log(f"保存汇总结果失败: {err}")
            return None

    def create_performance_charts(self, df, output_dir):
        """创建性能图表 - 添加电压相关图表"""
        try:
            plt.figure(figsize=(12, 10))
            
            # 频率-电压图
            plt.subplot(2, 2, 1)
            plt.plot(df['Avg_Actual_Freq(MHz)'], df['Avg_Voltage(V)'], 'mo-')
            plt.title('频率 vs 电压')
            plt.xlabel('实际频率 (MHz)')
            plt.ylabel('平均电压 (V)')
            plt.grid(True)
            
            # 电压-功耗图
            plt.subplot(2, 2, 2)
            plt.plot(df['Avg_Voltage(V)'], df['Avg_Power(W)'], 'co-')
            plt.title('电压 vs 功耗')
            plt.xlabel('平均电压 (V)')
            plt.ylabel('功耗 (W)')
            plt.grid(True)
            
            # 频率-功耗图
            plt.subplot(2, 2, 3)
            plt.plot(df['Avg_Actual_Freq(MHz)'], df['Avg_Power(W)'], 'go-', label='平均功耗')
            plt.title('频率 vs 功耗')
            plt.xlabel('目标频率 (MHz)')
            plt.ylabel('功耗 (W)')
            plt.legend()
            plt.grid(True)
            
            # 频率-分数图
            plt.subplot(2, 2, 4)
            plt.plot(df['Avg_Actual_Freq(MHz)'], df['Score'], 'bo-')
            plt.title('频率 vs 分数')
            plt.xlabel('目标频率 (MHz)')
            plt.ylabel('分数')
            plt.grid(True)
            
            plt.tight_layout()
            chart_path = os.path.join(output_dir, "performance_charts.png")
            plt.savefig(chart_path, dpi=150)
            self.log(f"性能图表已保存: {chart_path}")
            plt.close()
            
        except Exception as err:
            self.log(f"创建图表失败: {err}")

    def export_results(self):
        """导出结果到文件"""
        if not self.results:
            messagebox.showinfo("信息", "没有可导出的测试结果")
            return
            
        try:
            file_path = filedialog.asksaveasfilename(
                title="导出测试结果",
                defaultextension=".xlsx",
                filetypes=[("Excel文件", "*.xlsx"), ("CSV文件", "*.csv"), ("所有文件", "*.*")]
            )
            
            if not file_path:
                return
                
            # 创建DataFrame - 添加电压列
            df = pd.DataFrame(self.results, columns=[
                'Target_Freq(MHz)', 
                'Avg_Actual_Freq(MHz)', 
                'Avg_Power(W)', 
                'Max_Power(W)', 
                'Avg_Temp(C)', 
                'Max_Temp(C)', 
                'Score',
                'Avg_Voltage(V)'  # 添加平均电压
            ])
            
            # 根据文件扩展名保存
            if file_path.lower().endswith('.xlsx'):
                try:
                    df.to_excel(file_path, index=False, engine='openpyxl')
                except ImportError:
                    messagebox.showwarning("缺少依赖", "缺少openpyxl库，无法保存为Excel格式，将保存为CSV格式")
                    csv_path = file_path.replace('.xlsx', '.csv')
                    df.to_csv(csv_path, index=False)
                    file_path = csv_path
            elif file_path.lower().endswith('.csv'):
                df.to_csv(file_path, index=False)
            
            # 保存所有详细数据到单个文件
            output_dir = os.path.dirname(file_path)
            self.save_all_detailed_data(output_dir)
            
            # 创建图表
            self.create_performance_charts(df, output_dir)
            
            messagebox.showinfo("成功", f"结果已成功导出到:\n{file_path}")
            
        except Exception as e:
            messagebox.showerror("错误", f"导出结果失败: {str(e)}")

    def initialize_nvml(self):
        """初始化NVML库"""
        try:
            from pynvml import nvmlInit
            nvmlInit()
            self.nvml_initialized = True
            return True
        except ImportError:
            self.log("错误: pynvml库未安装，请运行 'pip install pynvml'")
            return False
        except Exception as e:
            self.log(f"NVML初始化失败: {str(e)}")
            return False

if __name__ == "__main__":
    try:
        root = tk.Tk()
        app = GPUPerformanceTester(root)
        root.mainloop()
    except Exception as e:
        messagebox.showerror("致命错误", f"应用程序启动失败: {str(e)}")