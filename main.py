import customtkinter as ctk
import psycopg2
from psycopg2.extras import RealDictCursor
import tkinter as tk
from tkinter import ttk, messagebox
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD
from decimal import Decimal, InvalidOperation
from datetime import datetime

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

style = ttk.Style()
style.theme_use("clam")
style.configure("Treeview", background="#2b2b2b", foreground="white", fieldbackground="#2b2b2b", rowheight=30)
style.configure("Treeview.Heading", background="#1f6aa5", foreground="white", font=("Arial", 11, "bold"))
style.map("Treeview", background=[("selected", "#1f6aa5")])

FIELD_NAMES = {
    "vat_rates": {
        "vat_code": "Код",
        "percentage": "Процент НДС",
        "description": "Описание"
    },
    "contract_types": {
        "contract_type_code": "Код",
        "type_name": "Тип договора"
    },
    "execution_stages": {
        "stage_code": "Код",
        "stage_name": "Стадия"
    },
    "payment_types": {
        "payment_type_code": "Код",
        "payment_type_name": "Вид оплаты"
    },
    "organizations": {
        "organization_code": "Код",
        "name": "Наименование",
        "postal_index": "Индекс",
        "address": "Адрес",
        "phone": "Телефон",
        "fax": "Факс",
        "inn": "ИНН",
        "correspondent_account": "Корр. счёт",
        "bank_name": "Банк",
        "settlement_account": "Расчётный счет",
        "okonh": "ОКОНХ",
        "okpo": "ОКПО",
        "bik": "БИК",
        "created_date": "Дата создания",
        "is_active": "Активна"
    },
    "contracts": {
        "contract_code": "Код",
        "conclusion_date": "Дата заключения",
        "customer_code": "Заказчик",
        "executor_code": "Исполнитель",
        "contract_type_code": "Тип договора",
        "execution_stage_code": "Стадия",
        "vat_code": "НДС",
        "execution_date": "План. дата",
        "topic": "Тема",
        "notes": "Примечание",
        "total_amount": "Сумма",
        "created_at": "Создано",
        "updated_at": "Обновлено"
    },
    "contract_stages": {
        "contract_code": "Код договора",
        "stage_number": "№ этапа",
        "stage_execution_date": "Дата этапа",
        "stage_code": "Стадия",
        "stage_amount": "Сумма этапа",
        "advance_amount": "Аванс",
        "topic": "Тема этапа",
        "notes": "Примечание"
    },
    "payments": {
        "payment_id": "Код",
        "contract_code": "Договор",
        "payment_date": "Дата платежа",
        "payment_amount": "Сумма",
        "payment_type_code": "Вид оплаты",
        "payment_document_number": "№ документа"
    }
}

menu_names = {
    "vat_rates": "Ставки НДС", "contract_types": "Типы договоров", "execution_stages": "Стадии",
    "payment_types": "Виды оплаты", "organizations": "Организации", "contracts": "Договоры",
    "contract_stages": "Этапы договоров", "payments": "Платежи"
}

class DatabaseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Система управления договорами")
        self.geometry("1500x900")

        try:
            self.conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
                                        user=DB_USER, password=DB_PASSWORD)
            self.cursor = self.conn.cursor(cursor_factory=RealDictCursor)
        except Exception as e:
            messagebox.showerror("Ошибка", f"Нет подключения к БД:\n{e}")
            raise

        self.current_table = None
        self.data = []
        self.filtered_data = []
        self.reference_cache = {}  
        self.sort_states = {}  

        self.create_widgets()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def on_closing(self):
        if self.conn:
            self.conn.close()
        self.destroy()

    def create_widgets(self):
        # ---------- ГЛАВНОЕ ОКНО ----------
        container = ctk.CTkFrame(self)
        container.pack(fill="both", expand=True)

        # ========== ЛЕВОЕ МЕНЮ ==========
        menu_frame = ctk.CTkFrame(container, width=260)
        menu_frame.pack(side="left", fill="y")
        menu_frame.pack_propagate(False)

        ctk.CTkLabel(
            menu_frame, 
            text="Навигация", 
            font=("Arial", 22, "bold")
        ).pack(pady=20)

        # --- секция таблиц ---
        ctk.CTkLabel(menu_frame, text="Таблицы", font=("Arial", 16, "bold")).pack(pady=(10, 5))

        for t in menu_names:
            ctk.CTkButton(
                menu_frame,
                text=menu_names[t],
                height=40,
                fg_color="#1f6aa5",
                hover_color="#155a88",
                font=("Arial", 14),
                command=lambda tbl=t: self.load_table(tbl)
            ).pack(fill="x", padx=15, pady=3)

        # --- секция отчётов ---
        ctk.CTkLabel(menu_frame, text="Отчёты", font=("Arial", 16, "bold")).pack(pady=(25, 5))

        ctk.CTkButton(
            menu_frame, text="Сведения по договорам",
            height=40, fg_color="#6c47ff", hover_color="#5538cc",
            font=("Arial", 14),
            command=self.report_contract_details
        ).pack(fill="x", padx=15, pady=3)

        ctk.CTkButton(
            menu_frame, text="Плановый график",
            height=40, fg_color="#6c47ff", hover_color="#5538cc",
            font=("Arial", 14),
            command=self.report_planned
        ).pack(fill="x", padx=15, pady=3)

        ctk.CTkButton(
            menu_frame, text="Фактические платежи",
            height=40, fg_color="#6c47ff", hover_color="#5538cc",
            font=("Arial", 14),
            command=self.report_actual
        ).pack(fill="x", padx=15, pady=3)


        # ========== ПРАВАЯ РАБОЧАЯ ОБЛАСТЬ ==========
        content = ctk.CTkFrame(container)
        content.pack(side="right", fill="both", expand=True, padx=5, pady=5)

        # Заголовок таблицы
        self.lbl = ctk.CTkLabel(
            content, 
            text="Выберите таблицу слева",
            font=("Arial", 24, "bold")
        )
        self.lbl.pack(pady=15)

        # ---------- ПОИСК И ФИЛЬТР ----------
        filter_frame = ctk.CTkFrame(content)
        filter_frame.pack(fill="x", pady=10)

        ctk.CTkLabel(filter_frame, text="Поиск:", font=("Arial", 14)).pack(side="left", padx=5)
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(filter_frame, textvariable=self.search_var, width=260)
        self.search_entry.pack(side="left", padx=10)
        self.search_entry.bind("<KeyRelease>", lambda e: self.apply_filters())


        ctk.CTkLabel(filter_frame, text="Фильтр:", font=("Arial", 14)).pack(side="left", padx=15)
        self.filter_col = ctk.CTkComboBox(filter_frame, width=200, values=[])
        self.filter_col.pack(side="left", padx=5)
        self.filter_val = ctk.CTkEntry(filter_frame, width=200)
        self.filter_val.pack(side="left", padx=10)
        self.filter_val.bind("<KeyRelease>", lambda e: self.apply_filters())


        # ---------- ТАБЛИЦА ----------
        table_frame = ctk.CTkFrame(content)
        table_frame.pack(fill="both", expand=True)

        self.tree = ttk.Treeview(table_frame, style="Treeview", show="headings")
        self.tree.pack(side="left", fill="both", expand=True)

        vsb = ctk.CTkScrollbar(table_frame, command=self.tree.yview)
        vsb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=vsb.set)


        # ---------- КНОПКИ ДЕЙСТВИЙ ----------
        btns = ctk.CTkFrame(content)
        btns.pack(fill="x", pady=10)

        ctk.CTkButton(btns, text="Добавить", height=40, fg_color="green",
                      font=("Arial", 14), command=self.add_record).pack(side="left", padx=8)

        ctk.CTkButton(btns, text="Изменить", height=40,
                      font=("Arial", 14), command=self.edit_record).pack(side="left", padx=8)

        ctk.CTkButton(btns, text="Удалить", height=40, fg_color="red",
                      hover_color="#aa2222", font=("Arial", 14),
                      command=self.delete_record).pack(side="left", padx=8)

        ctk.CTkButton(btns, text="Обновить", height=40,
                      font=("Arial", 14), command=self.refresh).pack(side="left", padx=8)


    def load_table(self, table):
        if table not in FIELD_NAMES:
            messagebox.showerror("Ошибка", "Неизвестная таблица")
            return

        self.current_table = table
        self.lbl.configure(text=f"Таблица: {menu_names[table]}")
        try:
            self.cursor.execute(f"SELECT * FROM {table}")
            rows = self.cursor.fetchall()
            self.data = []
            for row in rows:
                if isinstance(row, dict):
                    self.data.append(dict(row))
                else:
                    keys = [desc[0] for desc in self.cursor.description]
                    self.data.append(dict(zip(keys, row)))
            self.filtered_data = self.data.copy()
            self.setup_tree()
            self.populate_tree()

            # setup filter_col values to Russian names
            rus_fields = list(FIELD_NAMES.get(self.current_table, {}).values())
            self.filter_col.configure(values=rus_fields)
            if rus_fields:
                self.filter_col.set(rus_fields[0])
        except Exception as e:
            try:
                self.conn.rollback()
            except:
                pass
            messagebox.showerror("Ошибка загрузки", f"Не удалось загрузить таблицу {table}:\n{e}")
            self.data = []
            self.filtered_data = []

    def setup_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        self.tree["columns"] = ()

        if not self.data:
            return

        columns = list(FIELD_NAMES.get(self.current_table, {}).keys())
        self.tree["columns"] = columns

        # set headings
        for col in columns:
            rus = FIELD_NAMES[self.current_table].get(col, col)
            self.tree.heading(col, text=rus, command=lambda c=col: self.sort_by(c))
            width = 80 if col.endswith("_code") or col.endswith("_id") else 180
            anchor = "center" if col.endswith("_code") or col.endswith("_id") else "w"
            self.tree.column(col, width=width, anchor=anchor)

    def populate_tree(self):
        for i in self.tree.get_children():
            self.tree.delete(i)

        for row in self.filtered_data:
            values = []

            # определяем PK (для красоты)
            pk_col = next((k for k in row if k.endswith("_code") or k.endswith("_id") or k == "payment_id"), None)

            for col in self.tree["columns"]:
                val = row.get(col)

                # ---- PK ----
                if col == pk_col:
                    values.append("" if val is None else str(val))
                    continue

                # ---- FK отображение ----
                if col.endswith("_code") and col != pk_col:
                    disp = self.get_display(col, val)
                    values.append("" if disp is None else disp)
                    continue

                # ---- красивые даты ----
                if col in ("created_at", "updated_at", "created_date") and val:
                    try:
                        values.append(val.strftime("%d.%m.%Y"))
                    except:
                        s = str(val)
                        values.append(s.split()[0])
                    continue

                # ---- числа ----
                if isinstance(val, (int, float, Decimal)):
                    try:
                        values.append(f"{Decimal(val):.2f}")
                    except:
                        values.append(str(val))
                    continue

                # ---- текст ----
                values.append("" if val is None else str(val))

            self.tree.insert("", "end", values=values)


    def sort_by(self, col):
        # toggle sort state
        reverse = self.sort_states.get(col, False)
        # Use key that handles None
        def keyfn(r):
            v = r.get(col)
            return (v is None, v)
        self.filtered_data.sort(key=keyfn, reverse=not reverse)
        self.sort_states[col] = not reverse
        # update heading indicators (simple)
        for c in self.tree["columns"]:
            base = FIELD_NAMES[self.current_table].get(c, c)
            marker = ""
            if c == col:
                marker = " ↓" if self.sort_states[col] else " ↑"
            self.tree.heading(c, text=base + marker)
        self.populate_tree()

    def apply_filters(self, *_):
        # Если таблица не загружена — нечего фильтровать
        if not getattr(self, "data", None):
            return

        search = ""
        try:
            if hasattr(self, "search_entry") and self.search_entry is not None:
                search = (self.search_entry.get() or "").strip().lower()
        except Exception:
            search = ""

        if not search:
            try:
                search = (self.search_var.get() or "").strip().lower()
            except Exception:
                search = ""

        # --- 2) начинаем с полного набора данных ---
        result = list(self.data)

        # --- 3) "простой поиск" по всем полям ---
        if search:
            result = [
                r for r in result
                if any(search in str(v).lower() for v in r.values() if v is not None)
            ]

        # --- 4) фильтр по выбранному полю (как у тебя) ---
        # ВАЖНО: этот блок оставлен максимально совместимым — если чего-то нет, просто пропускаем.
        try:
            filt_col_disp = (self.filter_col.get() or "").strip()
            filt_val = (self.filter_val.get() or "").strip().lower()
        except Exception:
            filt_col_disp, filt_val = "", ""

        if filt_col_disp and filt_val and getattr(self, "current_table", None):
            try:
                eng_col = next(
                    (k for k, v in FIELD_NAMES[self.current_table].items() if v == filt_col_disp),
                    None
                )
            except Exception:
                eng_col = None

            if eng_col:
                result = [
                    r for r in result
                    if filt_val in str(r.get(eng_col, "")).lower()
                ]

        # --- 5) сохраняем и перерисовываем ---
        self.filtered_data = result
        self.populate_tree()


    # Unified get_display using cache
    def get_display(self, col, code):
        if code is None:
            return ""
        mapping = {
            "customer_code": ("organizations", "name", "organization_code"),
            "executor_code": ("organizations", "name", "organization_code"),
            "contract_type_code": ("contract_types", "type_name", "contract_type_code"),
            "execution_stage_code": ("execution_stages", "stage_name", "stage_code"),
            "vat_code": ("vat_rates", "description", "vat_code"),
            "payment_type_code": ("payment_types", "payment_type_name", "payment_type_code"),
            "stage_code": ("execution_stages", "stage_name", "stage_code"),
        }
        if col not in mapping:
            return str(code)
        tbl, field, code_col = mapping[col]
        cache_key = f"{tbl}_{field}"
        if cache_key not in self.reference_cache:
            # populate cache
            try:
                self.cursor.execute(f"SELECT {code_col}, {field} FROM {tbl}")
                rows = self.cursor.fetchall()
                cmap = {}
                clist = []
                for row in rows:
                    if isinstance(row, dict):
                        k = row[code_col]
                        v = row[field]
                    else:
                        k, v = row[0], row[1]
                    if k is None or v is None:
                        continue
                    cmap[k] = str(v)
                    clist.append(str(v))
                self.reference_cache[cache_key] = {"map": cmap, "list": sorted(list(set(clist)))}
            except Exception:
                return str(code)
        cmap = self.reference_cache[cache_key]["map"]
        # try direct and string key
        return cmap.get(code, cmap.get(str(code), str(code)))

    def add_record(self):
        if self.current_table == "contracts":
            self.add_contract_with_stages()
        else:
            self.edit_form("add")

    def edit_record(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите запись для редактирования")
            return
        item_id = sel[0]
        # find index by item_id position in displayed children
        try:
            idx = list(self.tree.get_children()).index(item_id)
        except ValueError:
            messagebox.showerror("Ошибка", "Не удалось найти выбранную запись")
            return
        if idx >= len(self.filtered_data):
            messagebox.showerror("Ошибка", "Неверный индекс записи")
            return
        self.edit_form("edit", self.filtered_data[idx])

    def delete_record(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Внимание", "Выберите запись для удаления")
            return
        if not messagebox.askyesno("Удаление", "Удалить запись?"):
            return
        item_id = sel[0]
        try:
            idx = list(self.tree.get_children()).index(item_id)
        except ValueError:
            messagebox.showerror("Ошибка", "Не удалось определить выбранную запись")
            return
        if not self.data:
            return
        pk = next(k for k in self.data[0] if k.endswith("_code") or k == "payment_id" or k.endswith("_id"))
        try:
            self.cursor.execute(f"DELETE FROM {self.current_table} WHERE {pk} = %s", (self.filtered_data[idx][pk],))
            self.conn.commit()
            self.invalidate_cache_for_table(self.current_table)
            self.refresh()
        except Exception as e:
            try:
                self.conn.rollback()
            except:
                pass
            messagebox.showerror("Ошибка", f"Не удалось удалить запись:\n{e}")

    def refresh(self):
        if self.current_table:
            self.load_table(self.current_table)

    def get_table_columns(self, table):
        try:
            self.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
            cols = [row["column_name"] for row in self.cursor.fetchall()]
            return [c for c in cols if c in FIELD_NAMES.get(table, {}) or c.endswith("_code") or c == "payment_id" or c.endswith("_id")]
        except Exception:
            try:
                self.conn.rollback()
            except:
                pass
            return []

    def edit_form(self, mode, data=None):

        win = ctk.CTkToplevel(self)
        win.title("Редактирование" if mode == "edit" else "Добавление")
        win.geometry("900x800")

        frame = ctk.CTkScrollableFrame(win)
        frame.pack(fill="both", expand=True, padx=20, pady=20)

        widgets = {}
        fields = FIELD_NAMES.get(self.current_table, {})

        # ---- Определяем PK поля таблицы ----
        pk_field = None
        for f in fields:
            if f.endswith("_code") or f == "payment_id" or f.endswith("_id"):
                pk_field = f
                break

        # ---- READONLY поля при редактировании ----
        readonly_fields = set()
        if mode == "edit":
            if pk_field:
                readonly_fields.add(pk_field)
        for f in ("created_date", "created_at", "updated_at"):
            if f in fields and mode == "edit":
                readonly_fields.add(f)

        # ---- Основной цикл по полям ----
        for field, label_text in fields.items():

            # --- при добавлении пропускаем PK и системные даты ---
            if mode == "add" and (field == pk_field or field in ("created_date", "created_at", "updated_at")):
                continue

            ctk.CTkLabel(frame, text=f"{label_text}:", anchor="w").pack(pady=(6, 2), anchor="w")

            # ---- READONLY отображение ----
            if field in readonly_fields:
                val = str(data.get(field)) if (data and field in data and data[field] is not None) else ""
                lbl = ctk.CTkLabel(frame, text=val, anchor="w")
                lbl.pack(fill="x", pady=2)
                widgets[field] = ("readonly", lbl)
                continue

            # ---- Boolean ----
            if field == "is_active":
                var = tk.BooleanVar(value=data.get(field) if (data and field in data) else True)
                cb = ctk.CTkCheckBox(frame, text="", variable=var)
                cb.pack(anchor="w", pady=2)
                widgets[field] = ("bool", var)
                continue

            # ---- Большие текстовые поля ----
            if field in ("notes", "address"):
                txt = ctk.CTkTextbox(frame, height=120)
                if data and data.get(field) is not None:
                    txt.insert("1.0", str(data[field]))
                txt.pack(fill="x", pady=4)
                widgets[field] = ("text", txt)
                continue

            # ---- FK-поля ----
            if field.endswith("_code") or field.endswith("_id"):
                vals = self.get_ref_list(field)
                combo = ctk.CTkComboBox(frame, values=vals)
                if data and data.get(field) is not None:
                    disp = self.get_display(field, data[field])
                    try: combo.set(disp)
                    except: pass
                combo.pack(fill="x", pady=2)
                widgets[field] = ("fk", combo)
                continue

            # ---- Даты ----
            if "date" in field:
                entry = ctk.CTkEntry(frame)
                if data and data.get(field):
                    entry.insert(0, str(data[field]))
                entry.pack(fill="x", pady=2)
                widgets[field] = ("date", entry)
                continue

            # ---- Числа ----
            if "amount" in field or "percentage" in field:
                entry = ctk.CTkEntry(frame)
                if data and data.get(field):
                    entry.insert(0, str(data[field]))
                entry.pack(fill="x", pady=2)
                widgets[field] = ("num", entry)
                continue

            # ---- Обычное текстовое поле ----
            entry = ctk.CTkEntry(frame)
            if data and data.get(field) is not None:
                entry.insert(0, str(data[field]))
            entry.pack(fill="x", pady=2)
            widgets[field] = ("text_short", entry)

        def save():
            values = {}

            for field, (wtype, w) in widgets.items():

                if wtype == "readonly":
                    continue

                if wtype == "bool":
                    values[field] = bool(w.get())
                    continue

                if wtype == "text":
                    content = w.get("1.0", "end").strip()
                    values[field] = content if content else None
                    continue

                if wtype == "fk":
                    disp = w.get()
                    values[field] = self.get_code_by_disp(field, disp)
                    continue

                try:
                    val = w.get().strip()
                except:
                    val = ""

                if val == "":
                    values[field] = None
                    continue

                if wtype == "num":
                    try:
                        values[field] = Decimal(val)
                    except:
                        messagebox.showerror("Ошибка", f"Поле {field} должно быть числом")
                        return

                elif wtype == "date":
                    try:
                        if "." in val:
                            dt = datetime.strptime(val, "%d.%m.%Y").date()
                        else:
                            dt = datetime.strptime(val, "%Y-%m-%d").date()
                        values[field] = dt
                    except:
                        messagebox.showerror("Ошибка", f"Поле {field} должно быть датой")
                        return
                else:
                    values[field] = val

            # ---- обязательные поля ----
            if self.current_table == "organizations" and not values.get("name"):
                messagebox.showerror("Ошибка", "Поле 'Наименование' обязательно")
                return

            if self.current_table == "contracts" and not values.get("topic"):
                messagebox.showerror("Ошибка", "Поле 'Тема' обязательно")
                return

            # ---- SQL ----
            try:
                if mode == "add":
                    keys = [k for k, v in values.items() if v is not None]
                    vals = [values[k] for k in keys]

                    if not keys:
                        messagebox.showerror("Ошибка", "Нет данных для вставки")
                        return

                    cols = ", ".join(keys)
                    ph = ", ".join(["%s"] * len(vals))
                    self.cursor.execute(f"INSERT INTO {self.current_table} ({cols}) VALUES ({ph})", vals)

                else:
                    if not pk_field:
                        messagebox.showerror("Ошибка", "PK не найден")
                        return

                    set_keys = [k for k in values if k != pk_field]
                    params = [values[k] for k in set_keys] + [data[pk_field]]
                    sets = ", ".join(f"{k}=%s" for k in set_keys)

                    self.cursor.execute(
                        f"UPDATE {self.current_table} SET {sets} WHERE {pk_field} = %s",
                        params
                    )

                self.conn.commit()
                self.invalidate_cache_for_table(self.current_table)
                win.destroy()
                self.refresh()

            except Exception as e:
                self.conn.rollback()
                messagebox.showerror("Ошибка", str(e))

        ctk.CTkButton(win, text="Сохранить", fg_color="green", command=save).pack(pady=15)



    def get_ref_list(self, col):
        mapping = {
            "customer_code": ("organizations", "name", "organization_code"),
            "executor_code": ("organizations", "name", "organization_code"),
            "contract_type_code": ("contract_types", "type_name", "contract_type_code"),
            "execution_stage_code": ("execution_stages", "stage_name", "stage_code"),
            "vat_code": ("vat_rates", "description", "vat_code"),
            "payment_type_code": ("payment_types", "payment_type_name", "payment_type_code"),
            "stage_code": ("execution_stages", "stage_name", "stage_code"),
            "contract_code": ("contracts", "topic", "contract_code")
        }
        if col not in mapping:
            return []
        tbl, field, code_col = mapping[col]
        key = f"{tbl}_{field}"
        if key not in self.reference_cache:
            try:
                self.cursor.execute(f"SELECT {code_col}, {field} FROM {tbl} ORDER BY {field}")
                rows = self.cursor.fetchall()
                cmap = {}
                clist = []
                for row in rows:
                    if isinstance(row, dict):
                        k = row[code_col]
                        v = row[field]
                    else:
                        k, v = row[0], row[1]
                    if k is None or v is None:
                        continue
                    cmap[k] = str(v)
                    clist.append(str(v))
                self.reference_cache[key] = {"map": cmap, "list": sorted(list(set(clist)))}
            except Exception:
                return []
        return self.reference_cache[key]["list"]

    def get_code_by_disp(self, col, disp):
        if not disp:
            return None
        mapping = {
            "customer_code": ("organizations", "name", "organization_code"),
            "executor_code": ("organizations", "name", "organization_code"),
            "contract_type_code": ("contract_types", "type_name", "contract_type_code"),
            "execution_stage_code": ("execution_stages", "stage_name", "stage_code"),
            "vat_code": ("vat_rates", "description", "vat_code"),
            "payment_type_code": ("payment_types", "payment_type_name", "payment_type_code"),
            "stage_code": ("execution_stages", "stage_name", "stage_code"),
            "contract_code": ("contracts", "topic", "contract_code")
        }
        if col not in mapping:
            return None
        tbl, field, code_col = mapping[col]
        cache_key = f"{tbl}_{field}"
        # try cache first
        if cache_key in self.reference_cache:
            cmap = self.reference_cache[cache_key]["map"]
            # reverse lookup
            for k, v in cmap.items():
                if str(v) == str(disp):
                    return k
        # otherwise query DB
        try:
            query = f"SELECT {code_col} FROM {tbl} WHERE {field} = %s LIMIT 1"
            self.cursor.execute(query, (disp,))
            result = self.cursor.fetchone()
            if not result:
                return None
            if isinstance(result, dict):
                return result.get(code_col)
            else:
                return result[0]
        except Exception:
            try:
                self.conn.rollback()
            except:
                pass
            return None

    def create_form(self, parent, table, exclude=None):
        exclude = exclude or []
        try:
            self.cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position", (table,))
            columns = [row["column_name"] for row in self.cursor.fetchall() if row["column_name"] not in exclude]
        except Exception:
            columns = []
        entries = {}
        for col in columns:
            label = ctk.CTkLabel(parent, text=col.capitalize())
            label.pack(pady=5)
            entry = ctk.CTkEntry(parent)
            entry.pack(pady=5)
            entries[col] = entry
        return entries

    def add_contract_with_stages(self):
        win = ctk.CTkToplevel(self)
        win.title("Создание договора с этапами")
        win.geometry("950x800")
        win.minsize(900, 700)

        # Главный скролл
        main_container = ctk.CTkScrollableFrame(win)
        main_container.pack(fill="both", expand=True, padx=15, pady=15)

        # === ДАННЫЕ ДОГОВОРА ===
        ctk.CTkLabel(main_container, text="ДАННЫЕ ДОГОВОРА", font=("Arial", 18, "bold")).pack(pady=(0, 10))

        contract_frame = ctk.CTkFrame(main_container)
        contract_frame.pack(fill="x", pady=10)

        contract_widgets = {}
        contract_fields = [
            "conclusion_date", "customer_code", "executor_code", "contract_type_code",
            "execution_stage_code", "vat_code", "execution_date", "topic", "notes", "total_amount"
        ]

        for i, field in enumerate(contract_fields):
            rus_name = FIELD_NAMES["contracts"].get(field, field)
            ctk.CTkLabel(contract_frame, text=f"{rus_name}:", anchor="w").grid(row=i, column=0, sticky="w", padx=10, pady=4)
            if field.endswith("_code"):
                combo = ctk.CTkComboBox(contract_frame, values=self.get_ref_list(field), width=400)
                combo.grid(row=i, column=1, padx=10, pady=4, sticky="ew")
                contract_widgets[field] = combo
            else:
                entry = ctk.CTkEntry(contract_frame, width=400)
                entry.grid(row=i, column=1, padx=10, pady=4, sticky="ew")
                contract_widgets[field] = entry
        contract_frame.columnconfigure(1, weight=1)

        # === ЭТАПЫ ===
        ctk.CTkLabel(main_container, text="ЭТАПЫ ДОГОВОРА", font=("Arial", 18, "bold")).pack(pady=(20, 5))

        stages_frame = ctk.CTkFrame(main_container)
        stages_frame.pack(fill="both", expand=True, pady=10)

        stages_list = []

        display_box = ctk.CTkTextbox(stages_frame, height=180, font=("Arial", 11))
        display_box.pack(fill="both", expand=True, padx=10, pady=5)
        display_box.insert("1.0", "Этапы ещё не добавлены...\n")
        display_box.configure(state="disabled")

        def update_display():
            display_box.configure(state="normal")
            display_box.delete("1.0", "end")
            if not stages_list:
                display_box.insert("1.0", "Этапы ещё не добавлены...\n")
            else:
                for i, stage in enumerate(stages_list, 1):
                    topic = stage.get("topic") or "Без темы"
                    amount = stage.get("stage_amount") or "0"
                    date = stage.get("stage_execution_date") or ""
                    display_box.insert("end", f"{i}. {topic} — {amount} руб. (план: {date})\n")
            display_box.configure(state="disabled")

        def add_stage():
            stage_win = ctk.CTkToplevel(win)
            stage_win.title("Новый этап")
            stage_win.geometry("700x650")

            stage_widgets = {}
            stage_fields = ["stage_number", "stage_execution_date", "stage_code", "stage_amount", "advance_amount", "topic", "notes"]

            for field in stage_fields:
                rus = FIELD_NAMES["contract_stages"].get(field, field)
                ctk.CTkLabel(stage_win, text=f"{rus}:", anchor="w").pack(pady=(10, 2), padx=20, anchor="w")
                if field == "stage_code":
                    combo = ctk.CTkComboBox(stage_win, values=self.get_ref_list("stage_code"), width=400)
                    combo.pack(pady=2, padx=20, fill="x")
                    stage_widgets[field] = combo
                else:
                    entry = ctk.CTkEntry(stage_win, width=400)
                    entry.pack(pady=2, padx=20, fill="x")
                    stage_widgets[field] = entry

            def save_stage():
                stage_data = {}
                for field, widget in stage_widgets.items():
                    val = ""
                    try:
                        val = widget.get().strip()
                    except Exception:
                        val = ""
                    if field == "stage_code":
                        val = self.get_code_by_disp(field, val)
                    elif val == "":
                        val = None
                    else:
                        if field in ("stage_amount", "advance_amount"):
                            try:
                                val = Decimal(val)
                            except InvalidOperation:
                                messagebox.showerror("Ошибка", f"Поле {field} должно быть числом")
                                return
                        elif "date" in field and val is not None:
                            try:
                                if "." in val:
                                    dt = datetime.strptime(val, "%d.%m.%Y").date()
                                else:
                                    dt = datetime.strptime(val, "%Y-%m-%d").date()
                                val = dt
                            except Exception:
                                messagebox.showerror("Ошибка", f"Поле {field} должно быть датой")
                                return
                    stage_data[field] = val
                # ensure unique stage_number for this contract's stages_list
                if any(s.get("stage_number") == stage_data.get("stage_number") for s in stages_list if stage_data.get("stage_number") is not None):
                    messagebox.showerror("Ошибка", "Этап с таким номером уже есть в списке")
                    return
                stages_list.append(stage_data)
                update_display()
                stage_win.destroy()

            ctk.CTkButton(stage_win, text="Сохранить этап", fg_color="green", command=save_stage).pack(pady=20)

        ctk.CTkButton(stages_frame, text="+ Добавить этап", fg_color="#0066cc", command=add_stage).pack(pady=8)

        # === СОХРАНЕНИЕ ===
        def save_all():
            contract_data = {}
            for field, widget in contract_widgets.items():
                try:
                    if field.endswith("_code"):
                        disp = widget.get()
                        contract_data[field] = self.get_code_by_disp(field, disp) if disp else None
                    else:
                        val = widget.get().strip()
                        if val == "":
                            contract_data[field] = None
                        else:
                            if "amount" in field:
                                try:
                                    contract_data[field] = Decimal(val)
                                except InvalidOperation:
                                    messagebox.showerror("Ошибка", f"Поле {field} должно быть числом")
                                    return
                            elif "date" in field:
                                try:
                                    if "." in val:
                                        dt = datetime.strptime(val, "%d.%m.%Y").date()
                                    else:
                                        dt = datetime.strptime(val, "%Y-%m-%d").date()
                                    contract_data[field] = dt
                                except Exception:
                                    messagebox.showerror("Ошибка", f"Поле {field} должно быть датой")
                                    return
                            else:
                                contract_data[field] = val
                except Exception:
                    contract_data[field] = None

            # minimal checks
            if not contract_data.get("topic"):
                messagebox.showerror("Ошибка", "Поле 'Тема' обязательно")
                return
            if not stages_list:
                messagebox.showwarning("Внимание", "Договор создаётся без этапов. Продолжить?")
                # allow empty stages

            # Insert contract + stages in one transaction
            try:
                cols = ", ".join(contract_data.keys())
                ph = ", ".join(["%s"] * len(contract_data))
                self.cursor.execute(
                    f"INSERT INTO contracts ({cols}) VALUES ({ph}) RETURNING contract_code",
                    list(contract_data.values())
                )
                result = self.cursor.fetchone()
                contract_id = result['contract_code'] if isinstance(result, dict) else result[0]

                for stage in stages_list:
                    stage["contract_code"] = contract_id
                    stage_cols = ", ".join(stage.keys())
                    stage_ph = ", ".join(["%s"] * len(stage))
                    self.cursor.execute(
                        f"INSERT INTO contract_stages ({stage_cols}) VALUES ({stage_ph})",
                        list(stage.values())
                    )
                self.conn.commit()
                self.invalidate_cache_for_table("contracts")
                self.invalidate_cache_for_table("contract_stages")
                messagebox.showinfo("Успех", "Договор сохранён!")
                win.destroy()
                self.refresh()
            except Exception as e:
                try:
                    self.conn.rollback()
                except:
                    pass
                messagebox.showerror("Ошибка", f"Не удалось сохранить:\n{e}")

        ctk.CTkButton(main_container, text="Сохранить договор и этапы", fg_color="green", font=("Arial", 14, "bold"), height=50, command=save_all).pack(pady=20)

        # -------------------- Параметры отчётов (фильтры + сортировка) --------------------

    REPORT_DEFS = {
        "contract_details": {
            "title": "Сведения по договорам",
            "fields": {
                # label: (sql_expression, type)
                "Код договора": ("c.contract_code", "int"),
                "Тема": ("c.topic", "text"),
                "№ этапа": ("cs.stage_number", "int"),
                "Сумма этапа": ("cs.stage_amount", "num"),
                "Оплачено по договору": ("COALESCE(pay.total_paid, 0)", "num"),
                "Дебиторка": ("(c.total_amount - COALESCE(pay.total_paid, 0))", "num"),
            },
            "default_sort": ("c.contract_code", "ASC"),
        },
        "planned": {
            "title": "Плановый график оплат по договорам",
            "fields": {
                "Код договора": ("c.contract_code", "int"),
                "Тема": ("c.topic", "text"),
                "План. дата": ("cs.stage_execution_date", "date"),
                "Сумма этапа": ("cs.stage_amount", "num"),
            },
            "default_sort": ("cs.stage_execution_date", "ASC"),
        },
        "actual": {
            "title": "Фактические поступления по договорам",
            "fields": {
                "Код договора": ("c.contract_code", "int"),
                "Тема": ("c.topic", "text"),
                "Дата платежа": ("p.payment_date", "date"),
                "Сумма платежа": ("p.payment_amount", "num"),
                "Вид оплаты": ("pt.payment_type_name", "text"),
                "№ документа": ("p.payment_document_number", "text"),
            },
            "default_sort": ("p.payment_date", "ASC"),
        },
    }

    def _build_where_and_order(self, report_key, f1, f2, sort_field_label, sort_dir):
        """
        f1/f2: dict with keys: enabled(bool), field_label(str), op(str), value(str)
        sort_field_label: Russian label from REPORT_DEFS[...]["fields"]
        sort_dir: "ASC"/"DESC"
        """
        rep = self.REPORT_DEFS[report_key]
        fields = rep["fields"]

        where_parts = []
        params = []

        def add_filter(f):
            if not f.get("enabled"):
                return
            label = f.get("field_label")
            op = f.get("op")
            raw = (f.get("value") or "").strip()
            if not label or label not in fields or raw == "":
                return

            expr, ftype = fields[label]

            # нормализуем оператор
            allowed_ops = {"=", ">=", "<=", "contains", "starts"}
            if op not in allowed_ops:
                return

            if ftype in ("int", "num"):
                try:
                    val = Decimal(raw) if ftype == "num" else int(raw)
                except Exception:
                    messagebox.showerror("Ошибка", f"Неверное значение для фильтра '{label}'")
                    raise
                if op in ("contains", "starts"):
                    messagebox.showerror("Ошибка", f"Оператор '{op}' не подходит для поля '{label}'")
                    raise
                where_parts.append(f"{expr} {op} %s")
                params.append(val)
                return

            if ftype == "date":
                try:
                    if "." in raw:
                        val = datetime.strptime(raw, "%d.%m.%Y").date()
                    else:
                        val = datetime.strptime(raw, "%Y-%m-%d").date()
                except Exception:
                    messagebox.showerror("Ошибка", f"Неверная дата для фильтра '{label}' (ожидается ДД.ММ.ГГГГ или ГГГГ-ММ-ДД)")
                    raise
                if op in ("contains", "starts"):
                    messagebox.showerror("Ошибка", f"Оператор '{op}' не подходит для поля '{label}'")
                    raise
                where_parts.append(f"{expr} {op} %s")
                params.append(val)
                return

            # text
            if op == "=":
                where_parts.append(f"{expr} = %s")
                params.append(raw)
            elif op == "contains":
                where_parts.append(f"{expr} ILIKE %s")
                params.append(f"%{raw}%")
            elif op == "starts":
                where_parts.append(f"{expr} ILIKE %s")
                params.append(f"{raw}%")
            else:
                messagebox.showerror("Ошибка", f"Оператор '{op}' не подходит для поля '{label}'")
                raise

        try:
            add_filter(f1)
            add_filter(f2)
        except Exception:
            # ошибки уже показали messagebox
            return None, None, None

        where_sql = ""
        if where_parts:
            where_sql = "WHERE " + " AND ".join(where_parts)

        # сортировка только из белого списка
        if sort_field_label and sort_field_label in fields:
            order_expr = fields[sort_field_label][0]
            order_dir = "DESC" if (sort_dir == "DESC") else "ASC"
        else:
            order_expr, order_dir = rep["default_sort"]

        order_sql = f"ORDER BY {order_expr} {order_dir}"

        return where_sql, order_sql, params

    def ask_report_params(self, report_key):
        """
        Возвращает (where_sql, order_sql, params) или (None, None, None) если отмена.
        """
        rep = self.REPORT_DEFS[report_key]
        fields_labels = list(rep["fields"].keys())

        win = ctk.CTkToplevel(self)
        win.title("Параметры отчёта")
        win.geometry("720x520")
        win.grab_set()  # модальное
        win.focus_force()

        ctk.CTkLabel(win, text=rep["title"], font=("Arial", 18, "bold")).pack(pady=(15, 10))

        # --- ФИЛЬТР 1 ---
        box1 = ctk.CTkFrame(win)
        box1.pack(fill="x", padx=15, pady=(10, 6))
        ctk.CTkLabel(box1, text="Фильтр 1", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        f1_enabled = tk.BooleanVar(value=False)
        c1 = ctk.CTkCheckBox(box1, text="включить", variable=f1_enabled)
        c1.grid(row=0, column=1, sticky="w", padx=10)

        f1_field = ctk.CTkComboBox(box1, values=fields_labels, width=240)
        f1_field.set(fields_labels[0] if fields_labels else "")
        f1_field.grid(row=1, column=0, padx=10, pady=6, sticky="w")

        f1_op = ctk.CTkComboBox(box1, values=["=", ">=", "<=", "contains", "starts"], width=130)
        f1_op.set("contains")
        f1_op.grid(row=1, column=1, padx=10, pady=6, sticky="w")

        f1_val = ctk.CTkEntry(box1, width=260, placeholder_text="значение")
        f1_val.grid(row=1, column=2, padx=10, pady=6, sticky="w")

        # --- ФИЛЬТР 2 ---
        box2 = ctk.CTkFrame(win)
        box2.pack(fill="x", padx=15, pady=(6, 10))
        ctk.CTkLabel(box2, text="Фильтр 2", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        f2_enabled = tk.BooleanVar(value=False)
        c2 = ctk.CTkCheckBox(box2, text="включить", variable=f2_enabled)
        c2.grid(row=0, column=1, sticky="w", padx=10)

        f2_field = ctk.CTkComboBox(box2, values=fields_labels, width=240)
        f2_field.set(fields_labels[0] if fields_labels else "")
        f2_field.grid(row=1, column=0, padx=10, pady=6, sticky="w")

        f2_op = ctk.CTkComboBox(box2, values=["=", ">=", "<=", "contains", "starts"], width=130)
        f2_op.set("contains")
        f2_op.grid(row=1, column=1, padx=10, pady=6, sticky="w")

        f2_val = ctk.CTkEntry(box2, width=260, placeholder_text="значение")
        f2_val.grid(row=1, column=2, padx=10, pady=6, sticky="w")

        # --- СОРТИРОВКА ---
        sort_box = ctk.CTkFrame(win)
        sort_box.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(sort_box, text="Сортировка", font=("Arial", 14, "bold")).grid(row=0, column=0, sticky="w", padx=10, pady=8)

        sort_field = ctk.CTkComboBox(sort_box, values=fields_labels, width=320)
        # ставим дефолт из репорта
        default_expr, default_dir = rep["default_sort"]
        # ищем label по expr (если найдём)
        default_label = None
        for lbl, (expr, _) in rep["fields"].items():
            if expr == default_expr:
                default_label = lbl
                break
        sort_field.set(default_label or (fields_labels[0] if fields_labels else ""))
        sort_field.grid(row=1, column=0, padx=10, pady=8, sticky="w")

        sort_dir = ctk.CTkComboBox(sort_box, values=["ASC", "DESC"], width=120)
        sort_dir.set(default_dir)
        sort_dir.grid(row=1, column=1, padx=10, pady=8, sticky="w")

        # --- КНОПКИ ---
        result = {"ok": False, "where": None, "order": None, "params": None}

        def on_ok():
            f1 = {"enabled": bool(f1_enabled.get()), "field_label": f1_field.get(), "op": f1_op.get(), "value": f1_val.get()}
            f2 = {"enabled": bool(f2_enabled.get()), "field_label": f2_field.get(), "op": f2_op.get(), "value": f2_val.get()}
            where_sql, order_sql, params = self._build_where_and_order(report_key, f1, f2, sort_field.get(), sort_dir.get())
            if where_sql is None:
                return
            result["ok"] = True
            result["where"] = where_sql
            result["order"] = order_sql
            result["params"] = params
            win.destroy()

        def on_cancel():
            win.destroy()

        btns = ctk.CTkFrame(win)
        btns.pack(fill="x", padx=15, pady=(15, 10))

        ctk.CTkButton(btns, text="Сформировать", fg_color="green", command=on_ok).pack(side="left", padx=10, pady=10)
        ctk.CTkButton(btns, text="Отмена", fg_color="#555", command=on_cancel).pack(side="left", padx=10, pady=10)

        self.wait_window(win)

        if not result["ok"]:
            return None, None, None
        return result["where"], result["order"], result["params"]

    
    # Отчёты
    def show_report(self, title, rows):
        win = ctk.CTkToplevel(self)
        win.title(title)
        win.geometry("1200x700")

        tree = ttk.Treeview(win, style="Treeview")
        tree.pack(fill="both", expand=True, padx=10, pady=10)

        if not rows:
            ctk.CTkLabel(win, text="Нет данных").pack()
            return

        # rows = list[dict]
        cols = list(rows[0].keys())
        tree["columns"] = cols
        tree["show"] = "headings"

        for c in cols:
            tree.heading(c, text=str(c).replace("_", " "))
            tree.column(c, width=170)

        for r in rows:
            tree.insert("", "end", values=[r.get(c) for c in cols])



    def report_contract_details(self):
        where_sql, order_sql, params = self.ask_report_params("contract_details")
        if where_sql is None:
            return  # отмена

        q = f"""
            SELECT 
                c.contract_code AS "Код договора",
                c.topic AS "Тема",
                cs.stage_number AS "№ этапа",
                cs.stage_amount AS "Сумма этапа",
                COALESCE(pay.total_paid, 0) AS "Оплачено по договору(итого)",
                (c.total_amount - COALESCE(pay.total_paid, 0)) AS "Дебиторская задолженность(итого)"
            FROM contracts c
            JOIN contract_stages cs 
                ON c.contract_code = cs.contract_code
            LEFT JOIN (
                SELECT contract_code, SUM(payment_amount) AS total_paid
                FROM payments
                GROUP BY contract_code
            ) pay ON c.contract_code = pay.contract_code
            {where_sql}
            {order_sql};
        """
        try:
            self.cursor.execute(q, params)
            rows = self.cursor.fetchall()
            self.show_report("Сведения по договорам", rows)
        except Exception as e:
            messagebox.showerror("Ошибка отчёта", str(e))


    def report_planned(self):
        where_sql, order_sql, params = self.ask_report_params("planned")
        if where_sql is None:
            return

        q = f"""
            SELECT 
                c.contract_code AS "Код договора",
                c.topic AS "Тема",
                cs.stage_execution_date AS "Плановая дата",
                cs.stage_amount AS "Сумма этапа"
            FROM contracts c
            JOIN contract_stages cs 
                ON c.contract_code = cs.contract_code
            {where_sql}
            {order_sql};
        """
        try:
            self.cursor.execute(q, params)
            rows = self.cursor.fetchall()
            self.show_report("Плановый график оплат по договорам", rows)
        except Exception as e:
            messagebox.showerror("Ошибка отчёта", str(e))


    def report_actual(self):
        where_sql, order_sql, params = self.ask_report_params("actual")
        if where_sql is None:
            return

        q = f"""
            SELECT 
                c.contract_code AS "Код договора",
                c.topic AS "Тема",
                p.payment_date AS "Дата платежа",
                p.payment_amount AS "Сумма платежа",
                pt.payment_type_name AS "Вид оплаты",
                p.payment_document_number AS "Номер документа"
            FROM contracts c
            JOIN payments p ON c.contract_code = p.contract_code
            JOIN payment_types pt ON p.payment_type_code = pt.payment_type_code
            {where_sql}
            {order_sql};
        """
        try:
            self.cursor.execute(q, params)
            rows = self.cursor.fetchall()
            self.show_report("Фактические поступления по договорам", rows)
        except Exception as e:
            messagebox.showerror("Ошибка отчёта", str(e))




    def invalidate_cache_for_table(self, table):
        # Remove any reference_cache keys related to table
        keys_to_remove = [k for k in self.reference_cache.keys() if k.startswith(table + "_") or ("contracts" if table=="contract_stages" else "")]
        for k in keys_to_remove:
            self.reference_cache.pop(k, None)

if __name__ == "__main__":
    app = DatabaseApp()
    app.mainloop()
