import pandas as pd
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QStackedWidget, 
    QLabel, QHeaderView, QCheckBox, QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QColor, QFont, QDrag

# IMPORTUJEME LOGIKU Z NAŠEHO PRVNÍHO SOUBORU
from data_processor import DataProcessor, get_duration, check_overlap

# --- POMOCNÁ TŘÍDA PRO DRAG & DROP ---
class DraggableTableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.oponent_mode = False 

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item:
                if self.oponent_mode:
                    super().mousePressEvent(event)
                    return
                
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(item.text())
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.CopyAction)
        super().mousePressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.accept()
        else: event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText(): event.accept()
        else: event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            pos = event.position().toPoint()
            item = self.itemAt(pos)
            if item:
                item.setText(event.mimeData().text())
                event.accept()
        else:
            event.ignore()

# --- MODUL B: UŽIVATELSKÉ ROZHRANÍ (GUI) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generátor zkušebních komisí")
        self.resize(1400, 850)
        self.processor = DataProcessor()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self.screen_import = QWidget()
        self.screen_availability = QWidget()
        self.screen_generate = QWidget()
        self.screen_edit = QWidget()
        
        self.setup_import_screen()
        self.setup_availability_screen()
        self.setup_generate_screen()
        self.setup_edit_screen()
        
        self.stack.addWidget(self.screen_import)      
        self.stack.addWidget(self.screen_availability)
        self.stack.addWidget(self.screen_generate)    
        self.stack.addWidget(self.screen_edit)        

    def setup_import_screen(self):
        layout = QVBoxLayout(self.screen_import)
        layout.addWidget(QLabel("<h2>1. Import a rozlišení milníků a studentů</h2>"))
        self.table_students = QTableWidget()
        layout.addWidget(self.table_students)
        
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Načíst data ze souborů")
        self.btn_load.clicked.connect(self.load_data_action)
        
        self.btn_to_avail = QPushButton("Pokračovat k dostupnosti členů ->")
        self.btn_to_avail.setEnabled(False)
        self.btn_to_avail.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        btn_layout.addWidget(self.btn_load)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_to_avail)
        layout.addLayout(btn_layout)

    def load_data_action(self):
        if self.processor.load_and_process("DoctoralThesis_CZ.xls", "DoctoralThesis_EN.xls", "phd_komise.xlsx"):
            self.refresh_student_table()
            self.refresh_availability_screen()
            self.btn_to_avail.setEnabled(True)
        else:
            QMessageBox.critical(self, "Chyba", "Nepodařilo se načíst data.")

    def refresh_student_table(self):
        self.table_students.setSortingEnabled(False)
        
        df = self.processor.students_df
        self.table_students.setRowCount(len(df))
        self.table_students.setColumnCount(8)
        self.table_students.setHorizontalHeaderLabels(["Zkouška", "Student", "Školitel", "Stav studia", "Stav DiP", "Milník", "Upřesnění", "Název práce"])
        
        for i, r in df.iterrows():
            student_name = str(r['Student'])
            
            cb_zkouska = QCheckBox()
            cb_zkouska.setChecked(bool(r['Zkouska_Aktivni']))
            cb_zkouska.stateChanged.connect(lambda s, name=student_name: self.update_zkouska_val(name, s))
            
            self.table_students.setItem(i, 0, QTableWidgetItem("")) 
            self.table_students.setCellWidget(i, 0, cb_zkouska)
            
            self.table_students.setItem(i, 1, QTableWidgetItem(student_name))
            self.table_students.setItem(i, 2, QTableWidgetItem(str(r['Školitel'])))
            self.table_students.setItem(i, 3, QTableWidgetItem(str(r['Stav studijního poměru'])))
            self.table_students.setItem(i, 4, QTableWidgetItem(str(r['Stav DiP'])))
            self.table_students.setItem(i, 5, QTableWidgetItem(str(r['Milník'])))
            
            if r['Milník'] == "1 nebo 2":
                cb_m2 = QCheckBox("M2")
                cb_m2.setChecked(r['M1_2_Volba'] == "2")
                cb_m2.stateChanged.connect(lambda s, name=student_name: self.update_milestone_val(name, s))
                self.table_students.setItem(i, 6, QTableWidgetItem(""))
                self.table_students.setCellWidget(i, 6, cb_m2)
            else:
                self.table_students.setItem(i, 6, QTableWidgetItem("-"))
                
            self.table_students.setItem(i, 7, QTableWidgetItem(str(r['Název DiP - česky'])))
            
        self.table_students.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_students.setSortingEnabled(True)

    def update_zkouska_val(self, student_name, state):
        idx = self.processor.students_df[self.processor.students_df['Student'] == student_name].index
        if not idx.empty:
            self.processor.students_df.loc[idx, 'Zkouska_Aktivni'] = (state == 2)

    def update_milestone_val(self, student_name, state): 
        idx = self.processor.students_df[self.processor.students_df['Student'] == student_name].index
        if not idx.empty:
            self.processor.students_df.loc[idx, 'M1_2_Volba'] = "2" if state == 2 else "1"

    def setup_availability_screen(self):
        layout = QVBoxLayout(self.screen_availability)
        layout.addWidget(QLabel("<h2>2. Filtrování dostupnosti (Kdo nemůže dorazit?)</h2><p>Odškrtněte lidi, kteří v termínu zkoušek nejsou k dispozici.</p>"))

        tables_layout = QHBoxLayout()

        layout_or = QVBoxLayout()
        layout_or.addWidget(QLabel("<b>Oborová rada (Předsedové)</b>"))
        self.table_or = QTableWidget()
        self.table_or.setColumnCount(2)
        self.table_or.setHorizontalHeaderLabels(["Dostupný", "Jméno"])
        self.table_or.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout_or.addWidget(self.table_or)

        layout_sk = QVBoxLayout()
        layout_sk.addWidget(QLabel("<b>Ostatní školitelé (Místopředsedové, Členové)</b>"))
        self.table_skolitel = QTableWidget()
        self.table_skolitel.setColumnCount(2)
        self.table_skolitel.setHorizontalHeaderLabels(["Dostupný", "Jméno"])
        self.table_skolitel.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout_sk.addWidget(self.table_skolitel)

        tables_layout.addLayout(layout_or)
        tables_layout.addLayout(layout_sk)
        layout.addLayout(tables_layout)

        btn_layout = QHBoxLayout()
        btn_back = QPushButton("<- Zpět na import")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_next = QPushButton("Uložit a pokračovat ke generování ->")
        btn_next.clicked.connect(self.save_availability_and_proceed)

        btn_layout.addWidget(btn_back)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_next)
        layout.addLayout(btn_layout)

    def refresh_availability_screen(self):
        self.table_or.setSortingEnabled(False)
        self.table_skolitel.setSortingEnabled(False)
        
        or_pool = self.processor.full_or_pool
        self.table_or.setRowCount(len(or_pool))
        for i, name in enumerate(or_pool):
            item_cb = QTableWidgetItem()
            item_cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_cb.setCheckState(Qt.CheckState.Checked) 
            self.table_or.setItem(i, 0, item_cb)
            self.table_or.setItem(i, 1, QTableWidgetItem(name))

        sk_pool = self.processor.full_skolitel_pool
        self.table_skolitel.setRowCount(len(sk_pool))
        for i, name in enumerate(sk_pool):
            item_cb = QTableWidgetItem()
            item_cb.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item_cb.setCheckState(Qt.CheckState.Checked) 
            self.table_skolitel.setItem(i, 0, item_cb)
            self.table_skolitel.setItem(i, 1, QTableWidgetItem(name))

        self.table_or.setSortingEnabled(True)
        self.table_skolitel.setSortingEnabled(True)

    def save_availability_and_proceed(self):
        active_or = []
        for i in range(self.table_or.rowCount()):
            if self.table_or.item(i, 0).checkState() == Qt.CheckState.Checked:
                active_or.append(self.table_or.item(i, 1).text())
        self.processor.active_or_pool = active_or

        active_sk = []
        for i in range(self.table_skolitel.rowCount()):
            if self.table_skolitel.item(i, 0).checkState() == Qt.CheckState.Checked:
                active_sk.append(self.table_skolitel.item(i, 1).text())
        self.processor.active_skolitel_pool = active_sk

        self.stack.setCurrentIndex(2)

    def setup_generate_screen(self):
        layout = QVBoxLayout(self.screen_generate)
        layout.addStretch()
        lbl = QLabel("<h1>3. Algoritmus připraven</h1>")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        
        btn_layout = QHBoxLayout()
        btn_back = QPushButton("<- Zpět k filtrům dostupnosti")
        btn_back.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        btn_gen = QPushButton("SPUSTIT GENEROVÁNÍ")
        btn_gen.setFixedSize(300,60)
        btn_gen.clicked.connect(self.run_algorithm)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)
        btn_layout.addWidget(btn_gen)
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        layout.addStretch()

    def run_algorithm(self): 
        self.processor.generate_schedule()
        self.refresh_results_tables()
        self.stack.setCurrentIndex(3)

    def setup_edit_screen(self):
        layout = QVBoxLayout(self.screen_edit)
        layout.addWidget(QLabel("<h2>4. Finální harmonogram a ruční editace (Oponenta určete vybráním buňky a kliknutím na tlačítko)</h2>"))
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.table_results = DraggableTableWidget()
        self.table_results.cellClicked.connect(self.on_table_cell_clicked)
        splitter.addWidget(self.table_results)
        
        pool_w = QWidget()
        p_lay = QVBoxLayout(pool_w)
        p_lay.addWidget(QLabel("<b>Dostupní členové (Filtrovaný seznam):</b>"))
        self.table_pool = DraggableTableWidget()
        p_lay.addWidget(self.table_pool)
        splitter.addWidget(pool_w)
        
        layout.addWidget(splitter)
        
        ctrl_layout = QHBoxLayout()
        
        self.oponent_mode = False
        self.btn_oponent = QPushButton("Oponent (Vypnuto)")
        self.btn_oponent.setStyleSheet("background-color: #fdebd0; font-weight: bold;")
        self.btn_oponent.clicked.connect(self.toggle_oponent_mode)
        
        btn_check = QPushButton("Zkontrolovat složení a časové konflikty")
        btn_check.setStyleSheet("background-color: #d1f2eb; font-weight: bold;")
        btn_check.clicked.connect(self.validate_schedule)
        
        btn_export = QPushButton("💾 Exportovat do Excelu")
        btn_export.setStyleSheet("background-color: #d4e6f1; font-weight: bold;")
        btn_export.clicked.connect(self.export_to_excel)
        
        btn_reset = QPushButton("Zpět ke generování")
        btn_reset.clicked.connect(lambda: self.stack.setCurrentIndex(2))
        
        ctrl_layout.addWidget(self.btn_oponent)
        ctrl_layout.addWidget(btn_check)
        ctrl_layout.addWidget(btn_export)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(btn_reset)
        
        layout.addLayout(ctrl_layout)

    def toggle_oponent_mode(self):
        self.oponent_mode = not self.oponent_mode
        self.table_results.oponent_mode = self.oponent_mode
        
        if self.oponent_mode:
            self.btn_oponent.setText("Oponent (ZAPNUTO - klikejte na jména)")
            self.btn_oponent.setStyleSheet("background-color: #f39c12; color: white; font-weight: bold;")
        else:
            self.btn_oponent.setText("Oponent (Vypnuto)")
            self.btn_oponent.setStyleSheet("background-color: #fdebd0; color: black; font-weight: bold;")

    def on_table_cell_clicked(self, row, col):
        if not self.oponent_mode:
            return 
            
        if 5 <= col <= 11:
            item = self.table_results.item(row, col)
            if not item: return
            
            text = item.text().strip()
            if not text or "KOLIZE" in text.upper() or "CHYBÍ" in text.upper():
                return
            
            if "[Oponent]" in text:
                text = text.replace(" [Oponent]", "").replace("[Oponent]", "").strip()
                item.setText(text)
            else:
                item.setText(text + " [Oponent]")
                
            self.apply_table_styles() 

    def apply_table_styles(self):
        or_members = set(self.processor.active_or_pool)
        for r in range(self.table_results.rowCount()):
            for c in range(5, 12):
                item = self.table_results.item(r, c)
                if not item: continue
                text = item.text().strip()
                if not text: continue
                
                is_oponent = "[Oponent]" in text
                clean_name = text.replace(" [Oponent]", "").replace("[Oponent]", "").strip()
                
                font = QFont()
                if is_oponent: 
                    font.setBold(True)
                item.setFont(font)
                
                if clean_name in or_members:
                    item.setBackground(QColor("#e6f2ff")) 
                elif "RUČNĚ" in text.upper():
                    item.setBackground(QColor("#eaeded"))
                else:
                    item.setBackground(QColor("white"))

    def refresh_results_tables(self):
        df = self.processor.schedule_df
        if not df.empty:
            df_cols = ["Den", "Čas", "Komise", "Student", "Milník", "Předseda", "Místopředseda", "Člen 1", "Člen 2", "Člen 3", "Člen 4", "Člen 5", "Přítomen (Školitel)"]
            ui_headers = ["Den", "Čas", "Komise", "Student", "M", "Předseda", "Místopředseda", "Člen 1", "Člen 2", "Člen 3", "Člen 4", "Člen 5", "Školitel"]
            
            self.table_results.setRowCount(len(df))
            self.table_results.setColumnCount(len(ui_headers))
            self.table_results.setHorizontalHeaderLabels(ui_headers)
            
            for i, r in df.iterrows():
                for j, col in enumerate(df_cols):
                    val = r.get(col, "")
                    item = QTableWidgetItem(str(val))
                    self.table_results.setItem(i, j, item)
            
            self.apply_table_styles()
            self.table_results.resizeColumnsToContents()

        df_p = self.processor.pool_df
        if not df_p.empty:
            self.table_pool.setRowCount(len(df_p))
            self.table_pool.setColumnCount(2)
            self.table_pool.setHorizontalHeaderLabels(["Jméno", "Role"])
            for i, r in df_p.iterrows():
                n_it = QTableWidgetItem(str(r['Jméno']))
                r_it = QTableWidgetItem(str(r['Role']))
                if r['Role'] == "Oborová rada": 
                    n_it.setBackground(QColor("#e6f2ff"))
                self.table_pool.setItem(i, 0, n_it)
                self.table_pool.setItem(i, 1, r_it)
            self.table_pool.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def validate_schedule(self):
        conflicts = []; missing = []; presence_map = {} 
        or_members = set(self.processor.active_or_pool)

        for row in range(self.table_results.rowCount()):
            den = self.table_results.item(row, 0).text()
            cas = self.table_results.item(row, 1).text()
            mistnost = self.table_results.item(row, 2).text()
            student = self.table_results.item(row, 3).text()
            milnik = self.table_results.item(row, 4).text()
            skolitel = self.table_results.item(row, 12).text()
            
            duration = get_duration(milnik)
            start_dt = datetime.strptime(cas, "%H:%M")
            end_dt = start_dt + timedelta(minutes=duration)
            
            seen_in_this_commission = set()
            
            members_count = 0
            or_count = 0
            ext_count = 0
            op_count = 0

            for col in range(5, 12):
                item = self.table_results.item(row, col)
                if not item: continue
                text = item.text().strip()
                
                if not text or "KOLIZE" in text.upper() or "CHYBÍ" in text.upper(): continue
                
                members_count += 1
                
                clean_name = text.replace(" [Oponent]", "").replace("[Oponent]", "").strip()
                if clean_name in or_members: or_count += 1
                if "EXTERNISTA" in text.upper(): ext_count += 1
                if "[OPONENT]" in text.upper(): op_count += 1
                
                if "RUČNĚ" in text.upper(): continue
                
                if clean_name == skolitel:
                    conflicts.append(f"Student {student}: {clean_name} je školitel! Nesmí být členem komise.")
                    item.setBackground(QColor("#f5b7b1")) 
                if clean_name in seen_in_this_commission:
                    conflicts.append(f"Duplicita: {clean_name} je ve stejné komisi ({mistnost}, {cas}) vícekrát!")
                    item.setBackground(QColor("#f5b7b1")) 
                else: seen_in_this_commission.add(clean_name)

                key = (den, clean_name)
                if key in presence_map:
                    for (s, e, mist) in presence_map[key]:
                        if check_overlap(start_dt, end_dt, s, e) and mistnost != mist:
                            conflicts.append(f"Časový překryv: {clean_name} má konflikt v čase {cas} ({den}). Místnosti: {mistnost} a {mist}")
                            item.setBackground(QColor("#f5b7b1")) 
                    presence_map[key].append((start_dt, end_dt, mistnost))
                else: 
                    presence_map[key] = [(start_dt, end_dt, mistnost)]

            m = milnik.replace("M", "").strip() 
            
            if m in ['1', '3']:
                if members_count < 3: missing.append(f"Student {student}: Minimum 3 členové! Nyní: {members_count}")
                if or_count < 1: missing.append(f"Student {student}: Chybí zástupce Oborové rady!")
            elif m == '2':
                if members_count < 5: missing.append(f"Student {student}: Minimum 5 členů! Nyní: {members_count}")
                if or_count < 1: missing.append(f"Student {student}: Chybí zástupce Oborové rady!")
                if ext_count < 1: missing.append(f"Student {student}: Chybí minimálně 1 Externista!")
                if op_count < 1: missing.append(f"Student {student}: Označte minimálně 1 člena jako [Oponent]!")
            elif m == '4':
                if members_count < 5: missing.append(f"Student {student}: Minimum 5 členů! Nyní: {members_count}")
                if or_count < 1: missing.append(f"Student {student}: Chybí zástupce Oborové rady!")
                if ext_count < 2: missing.append(f"Student {student}: Chybí minimálně 2 Externisté!")
                if op_count < 3: missing.append(f"Student {student}: Označte minimálně 3 členy jako [Oponent]!")

        if not conflicts and not missing: 
            QMessageBox.information(self, "Validace OK", "Excelentní! Harmonogram nemá žádné konflikty.\n\nKomise splňují všechna pravidla a počty členů.")
            self.apply_table_styles() 
        else:
            err_msg = "Nalezeny problémy, tabulka je barevně zvýrazněna:\n\n"
            if conflicts: err_msg += "KRITICKÉ KONFLIKTY:\n" + "\n".join(set(conflicts)) + "\n\n"
            if missing: err_msg += "CHYBĚJÍCÍ OBSAZENÍ / PRAVIDLA:\n" + "\n".join(set(missing))
            QMessageBox.warning(self, "Chyba ve složení", err_msg)

    def export_to_excel(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "Uložit harmonogram jako...", 
            "Harmonogram_Komise.xlsx", 
            "Excel Soubory (*.xlsx)"
        )
        
        if not file_path:
            return 

        try:
            rows = self.table_results.rowCount()
            cols = self.table_results.columnCount()
            headers = [self.table_results.horizontalHeaderItem(i).text() for i in range(cols)]
            
            data = []
            for r in range(rows):
                row_data = []
                for c in range(cols):
                    item = self.table_results.item(r, c)
                    row_data.append(item.text().strip() if item else "")
                data.append(row_data)
                
            df_export = pd.DataFrame(data, columns=headers)
            df_export.to_excel(file_path, index=False, engine='openpyxl')
            
            QMessageBox.information(self, "Úspěch", f"Data byla úspěšně vyexportována a uložena do:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Chyba při ukládání", f"Nastala chyba:\n{e}")