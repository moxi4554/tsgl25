import os
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
from pathlib import Path
import hashlib
from collections import defaultdict

class LibraryExpertSystemV14_9:
    def __init__(self, root):
        self.root = root
        self.root.title("圖書管理專家系統 v14.9 - 重複檔案智能處理版")
        self.root.geometry("1680x1080")

        self.current_src_dir = None
        self.target_base = Path(r'G:\qilib')

        self.last_clicked_item = None
        self.shift_anchor = None

        self.setup_ui()

    def setup_ui(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # ==================== 左側 ====================
        left_frame = ttk.LabelFrame(paned, text=" 1. 源文件區域 (單擊勾選 / Shift+單擊範圍勾選 / 滾輪滾動) ", padding="8")
        paned.add(left_frame, weight=3)

        btn_bar = ttk.Frame(left_frame)
        btn_bar.pack(fill=tk.X, pady=(0, 8))

        ttk.Button(btn_bar, text="📁 開啟目錄", command=self.select_root).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="⬅️ 返回上層", command=self.go_back).pack(side=tk.LEFT, padx=3)
        ttk.Button(btn_bar, text="✅ 全選", command=self.select_all).pack(side=tk.LEFT, padx=8)
        ttk.Button(btn_bar, text="❌ 取消全選", command=self.deselect_all).pack(side=tk.LEFT, padx=3)

        ttk.Button(btn_bar, text="📦 按鈕1：整體移動勾選的資料夾", 
                   command=self.move_folders_batch).pack(side=tk.LEFT, padx=12)   # 第41行
        ttk.Button(btn_bar, text="🔍 按鈕2：進入藍條選中的目錄", 
                   command=self.enter_folder).pack(side=tk.LEFT, padx=3)

        self.src_tree = ttk.Treeview(left_frame, columns=("check", "name", "type", "path"), show="headings")
        self.src_tree.heading("check", text="勾選")
        self.src_tree.heading("name", text="名稱")
        self.src_tree.heading("type", text="類型")
        self.src_tree.heading("path", text="完整路徑")

        self.src_tree.column("check", width=70, anchor="center")
        self.src_tree.column("name", width=520)
        self.src_tree.column("type", width=90, anchor="center")
        self.src_tree.column("path", width=0, stretch=tk.NO)

        self.src_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        self.src_tree.bind("<Button-1>", self.on_left_click)
        self.src_tree.bind("<Button-3>", self.on_right_click)
        self.src_tree.bind("<Double-1>", lambda e: self.enter_folder())
        self.src_tree.bind("<MouseWheel>", self.on_mouse_wheel)

        self.src_context_menu = tk.Menu(self.root, tearoff=0)
        self.src_context_menu.add_command(label="🗑️ 刪除選中空資料夾", command=self.delete_src_folder)

        # ==================== 右側 ====================
        right_frame = ttk.LabelFrame(paned, text=" 2. 目標庫目錄樹 (右鍵可新建/重命名/刪除空資料夾) ", padding="8")
        paned.add(right_frame, weight=2)

        self.dest_tree = ttk.Treeview(right_frame, show="tree")
        self.dest_tree.pack(fill=tk.BOTH, expand=True)
        self.refresh_dest_tree()

        self.dest_context_menu = tk.Menu(self.root, tearoff=0)
        self.dest_context_menu.add_command(label="新建資料夾", command=self.create_new_folder)
        self.dest_context_menu.add_command(label="重新命名", command=self.rename_folder)
        self.dest_context_menu.add_separator()
        self.dest_context_menu.add_command(label="🗑️ 刪除資料夾（僅限空）", command=self.delete_dest_folder)

        self.dest_tree.bind("<Button-3>", self.show_dest_context_menu)
        self.dest_tree.bind("<ButtonRelease-3>", self.show_dest_context_menu)

        # ==================== 底部 ====================
        bottom = ttk.Frame(self.root, padding="10")
        bottom.pack(fill=tk.X)

        self.auto_clean = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom, text="自動清理名稱", variable=self.auto_clean).pack(side=tk.LEFT, padx=15)

        ttk.Button(bottom, text="🚀 批量移動勾選的檔案", 
                   command=self.move_checked_files_batch).pack(side=tk.RIGHT, padx=10)

        ttk.Button(bottom, text="📄 移動藍條單個檔案", 
                   command=self.move_selected_single_file).pack(side=tk.RIGHT, padx=8)

        self.pbar = ttk.Progressbar(bottom, orient=tk.HORIZONTAL, mode='determinate')
        self.pbar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

    # ====================== 左側事件 ======================
    def on_left_click(self, event):
        item_id = self.src_tree.identify_row(event.y)
        if not item_id: return
        column = self.src_tree.identify_column(event.x)
        is_shift = bool(event.state & 0x0001)

        if is_shift and self.shift_anchor:
            self.range_select(self.shift_anchor, item_id)
        else:
            if column == "#1":
                self.toggle_item(item_id)
            self.last_clicked_item = item_id
            self.shift_anchor = item_id

    def on_right_click(self, event):
        item_id = self.src_tree.identify_row(event.y)
        if not item_id: return
        is_shift = bool(event.state & 0x0001)

        if is_shift and self.shift_anchor:
            self.range_select(self.shift_anchor, item_id)
        else:
            self.src_tree.selection_set(item_id)
            self.src_tree.focus(item_id)
            self.src_context_menu.post(event.x_root, event.y_root)

        self.last_clicked_item = item_id
        self.shift_anchor = item_id

    def range_select(self, start_item, end_item):
        all_items = self.src_tree.get_children()
        if not all_items: return
        try:
            s = all_items.index(start_item)
            e = all_items.index(end_item)
            if s > e: s, e = e, s
            for i in range(s, e + 1):
                vals = list(self.src_tree.item(all_items[i], "values"))
                vals[0] = " [√]"
                self.src_tree.item(all_items[i], values=vals)
        except: pass

    def toggle_item(self, item_id):
        vals = list(self.src_tree.item(item_id, "values"))
        vals[0] = " [√]" if vals[0].strip() == "[ ]" else " [ ]"
        self.src_tree.item(item_id, values=vals)

    # ====================== 重複內容檢測與處理 ======================
    def get_file_signature(self, file_path: Path):
        try:
            size = file_path.stat().st_size
            with open(file_path, 'rb') as f:
                content = f.read(8192)
            hash_val = hashlib.md5(content).hexdigest()
            return (size, hash_val)
        except:
            return (0, "")

    def move_checked_files_batch(self):
        checked_items = [i for i in self.src_tree.get_children() 
                        if "[√]" in self.src_tree.item(i)['values'][0]]
        
        dest_sel = self.dest_tree.selection()
        if not checked_items:
            messagebox.showwarning("提示", "請先勾選要移動的檔案！")
            return
        if not dest_sel:
            messagebox.showwarning("提示", "請在右側選中一個目標位置！")
            return

        dest_dir = Path(self.dest_tree.item(dest_sel[0])['values'][0])

        file_list = []
        for item_id in checked_items:
            vals = self.src_tree.item(item_id, 'values')
            old_path = Path(vals[3])
            if old_path.is_dir(): continue
            file_list.append((item_id, old_path))

        content_groups = defaultdict(list)
        for item_id, path in file_list:
            sig = self.get_file_signature(path)
            content_groups[sig].append((item_id, path))

        success = 0
        moved_to_dup = 0

        for sig, group in content_groups.items():
            if len(group) == 1:
                item_id, old_path = group[0]
                final_target = self.handle_duplicate_file(old_path, dest_dir)
                if final_target and self.try_move(old_path, final_target):
                    self.src_tree.delete(item_id)
                    success += 1
            else:
                msg = f"發現 {len(group)} 個內容完全相同的檔案：\n\n"
                for _, p in group:
                    msg += f"• {p.name}\n"
                msg += "\n系統將只移動其中一個到目標資料夾，其餘自動放入「重複檔案」資料夾。"

                if messagebox.askyesno("內容重複檢測", msg, default=messagebox.YES):
                    first = True
                    for item_id, old_path in group:
                        if first:
                            final_target = self.handle_duplicate_file(old_path, dest_dir)
                            if final_target and self.try_move(old_path, final_target):
                                self.src_tree.delete(item_id)
                                success += 1
                            first = False
                        else:
                            dup_folder = dest_dir / "重複檔案"
                            dup_folder.mkdir(exist_ok=True)
                            dup_target = dup_folder / old_path.name
                            count = 1
                            while dup_target.exists():
                                dup_target = dup_folder / f"{old_path.stem}_副本{count}{old_path.suffix}"
                                count += 1
                            try:
                                shutil.move(str(old_path), str(dup_target))
                                self.src_tree.delete(item_id)
                                moved_to_dup += 1
                            except: pass

        messagebox.showinfo("完成", f"移動完成！\n成功移動到目標：{success} 個\n移入重複檔案資料夾：{moved_to_dup} 個")

        if not self.src_tree.get_children():
            self.go_back()

    def try_move(self, src, dst):
        try:
            shutil.move(str(src), str(dst))
            return True
        except:
            return False

    def handle_duplicate_file(self, src_path: Path, dest_dir: Path) -> Path:
        clean_stem = self._clean_name(src_path.stem)
        target_path = dest_dir / (clean_stem + src_path.suffix)

        if not target_path.exists():
            return target_path

        choice = messagebox.askyesnocancel(
            "目標位置已存在相同檔名",
            f"目標資料夾中已存在：\n{target_path.name}\n\n"
            "請選擇：\n"
            "• 是 → 覆蓋目標原有檔案\n"
            "• 否 → 跳過此檔案\n"
            "• 取消 → 把來源檔案移入「重複檔案」資料夾",
            default=messagebox.CANCEL
        )

        if choice is True: return target_path
        if choice is False: return None

        dup_folder = dest_dir / "重複檔案"
        dup_folder.mkdir(exist_ok=True)
        count = 1
        while True:
            new_name = f"{clean_stem}_副本{count}{src_path.suffix}"
            new_path = dup_folder / new_name
            if not new_path.exists():
                return new_path
            count += 1

    def _clean_name(self, name: str) -> str:
        if not self.auto_clean.get(): return name.strip()
        res = name.strip()
        res = re.sub(r'^\s*\d{3}\s*[.．]?\s*', '', res)
        res = re.sub(r'^[a-zA-Z0-9]+\s*[.．]\s*', '', res)
        res = re.sub(r'\[.*?\]|\(.*?\)|【.*?】|（.*?）|「.*?」', '', res)
        res = re.sub(r'[<>: "/\\|?*]', '', res)
        res = re.sub(r'[\s._\-]+', ' ', res)
        return res.strip(' ._-')

    # ====================== 右鍵功能 ======================
    def show_dest_context_menu(self, event):
        item = self.dest_tree.identify_row(event.y)
        if item:
            self.dest_tree.selection_set(item)
        self.dest_context_menu.post(event.x_root, event.y_root)

    def delete_dest_folder(self):
        sel = self.dest_tree.selection()
        if not sel: return
        folder = Path(self.dest_tree.item(sel[0])['values'][0])
        if not folder.is_dir() or any(folder.iterdir()):
            messagebox.showwarning("無法刪除", "只能刪除空資料夾")
            return
        if messagebox.askyesno("確認", f"刪除空資料夾？\n{folder.name}"):
            try:
                folder.rmdir()
                self.refresh_dest_tree()
            except Exception as e:
                messagebox.showerror("錯誤", str(e))

    def create_new_folder(self):
        sel = self.dest_tree.selection()
        if not sel: return
        parent = Path(self.dest_tree.item(sel[0])['values'][0])
        name = simpledialog.askstring("新建資料夾", "輸入名稱：", initialvalue="新資料夾")
        if name and name.strip():
            (parent / name.strip()).mkdir(parents=True, exist_ok=True)
            self.refresh_dest_tree()

    def rename_folder(self):
        sel = self.dest_tree.selection()
        if not sel: return
        old = Path(self.dest_tree.item(sel[0])['values'][0])
        name = simpledialog.askstring("重命名", "新名稱：", initialvalue=old.name)
        if name and name.strip() != old.name:
            try:
                old.rename(old.parent / name.strip())
                self.refresh_dest_tree()
            except Exception as e:
                messagebox.showerror("錯誤", str(e))

    def delete_src_folder(self):
        sel = self.src_tree.selection()
        if not sel: return
        path = Path(self.src_tree.item(sel[0], 'values')[3])
        if not path.is_dir() or any(path.iterdir()):
            messagebox.showwarning("無法刪除", "只能刪除空資料夾")
            return
        if messagebox.askyesno("確認", f"刪除空資料夾？\n{path.name}"):
            try:
                path.rmdir()
                self.src_tree.delete(sel[0])
            except Exception as e:
                messagebox.showerror("錯誤", str(e))

    def on_mouse_wheel(self, event):
        self.src_tree.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def select_all(self):
        for item in self.src_tree.get_children():
            vals = list(self.src_tree.item(item, "values"))
            vals[0] = " [√]"
            self.src_tree.item(item, values=vals)

    def deselect_all(self):
        for item in self.src_tree.get_children():
            vals = list(self.src_tree.item(item, "values"))
            vals[0] = " [ ]"
            self.src_tree.item(item, values=vals)

    def enter_folder(self):
        sel = self.src_tree.selection()
        if not sel: return
        p = Path(self.src_tree.item(sel[0], 'values')[3])
        if p.is_dir():
            self.load_src_dir(p)

    def select_root(self):
        d = filedialog.askdirectory(title="選擇源文件根目錄")
        if d:
            self.load_src_dir(Path(d))

    def load_src_dir(self, path: Path):
        self.current_src_dir = path
        self.src_tree.delete(*self.src_tree.get_children())
        self.last_clicked_item = None
        self.shift_anchor = None
        try:
            for entry in sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                if entry.name.startswith('.'): continue
                ftype = "📁 資料夾" if entry.is_dir() else "📄 文件"
                self.src_tree.insert("", "end", values=(" [ ]", entry.name, ftype, str(entry)))
        except Exception as e:
            messagebox.showerror("錯誤", str(e))

    def go_back(self):
        if self.current_src_dir and self.current_src_dir.parent != self.current_src_dir:
            self.load_src_dir(self.current_src_dir.parent)

    def refresh_dest_tree(self):
        self.dest_tree.delete(*self.dest_tree.get_children())
        root_id = self.dest_tree.insert("", "end", text=f"📚 圖書庫 ({self.target_base.name})", 
                                      open=True, values=(str(self.target_base),))
        def build(parent_id, p: Path):
            try:
                for item in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
                    if item.is_dir() and not item.name.startswith('.'):
                        node = self.dest_tree.insert(parent_id, "end", text=item.name, values=(str(item),))
                        build(node, item)
            except: pass
        build(root_id, self.target_base)

    # ====================== 補全缺失的方法 ======================
    def move_folders_batch(self):
        messagebox.showinfo("提示", "按鈕1（整體移動資料夾）功能暫未完整實作")

    def move_selected_single_file(self):
        messagebox.showinfo("提示", "單檔移動功能暫未完整實作")


if __name__ == "__main__":
    root = tk.Tk()
    app = LibraryExpertSystemV14_9(root)
    root.mainloop()