import sys
import pandas as pd
import logging
import itertools
from datetime import datetime, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QTableWidget, QTableWidgetItem, QPushButton, QStackedWidget, 
    QLabel, QHeaderView, QCheckBox, QMessageBox, QSplitter, QFileDialog
)
from PyQt6.QtCore import Qt, QMimeData
from PyQt6.QtGui import QColor, QFont, QDrag

# --- KONFIGURACE LOGOVÁNÍ ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

# --- POMOCNÁ TŘÍDA PRO DRAG & DROP ---
class DraggableTableWidget(QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item:
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

# --- MODUL A & C: DATA PROCESSING A ALGORITMUS ---
class DataProcessor:
    def __init__(self):
        self.students_df = pd.DataFrame()
        self.komise_df = dict()
        self.schedule_df = pd.DataFrame()
        self.pool_df = pd.DataFrame()

    def load_and_process(self, cz_file_path, en_file_path, komise_file_path):
        try:
            df_cz = pd.read_excel(cz_file_path, skiprows=10)
            df_en = pd.read_excel(en_file_path, skiprows=10)
            self.komise_df = pd.read_excel(komise_file_path, sheet_name=None, engine='openpyxl')
            df_all = pd.concat([df_cz, df_en], ignore_index=True)
            df_all.columns = df_all.columns.astype(str).str.strip()
            self._process_students(df_all)
            return True
        except Exception as e:
            logging.error(f"Chyba při načítání dat: {e}")
            return False

    def _process_students(self, df: pd.DataFrame):
        df['Stav_Normalizovany'] = df['Stav studijního poměru'].astype(str).str.strip().str.lower()
        maska_aktivni = df['Stav_Normalizovany'].str.contains('studuje', na=False) & df['Stav_Normalizovany'].str.contains('ročník', na=False)
        df_active = df[maska_aktivni].copy()
        columns_to_keep = ['Školitel', 'Student', 'Stav studijního poměru', 'Název DiP - česky', 'Název DiP - anglicky', 'Stav DiP']
        df_filtered = df_active[columns_to_keep].copy()
        df_filtered = df_filtered.replace({r'\r\n': ' ', r'\n': ' ', r'\r': ' '}, regex=True)
        df_filtered['Milník'] = df_filtered['Stav DiP'].apply(self._determine_milestone)
        df_filtered['M1_2_Volba'] = "1" 
        self.students_df = df_filtered.reset_index(drop=True)

    def _determine_milestone(self, stav_dip):
        stav = str(stav_dip).strip()
        if stav == "Teze zadány": return "1 nebo 2"
        if stav == "DiP k zadání": return "3"
        if stav == "DiP zadána": return "4"
        return "Nespecifikováno"

    def _parse_pools(self):
        or_pool, skolitel_pool = [], []
        for sheet_name, df in self.komise_df.items():
            if df.empty: continue
            vals = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
            if 'rada' in str(sheet_name).lower() or 'oborov' in str(sheet_name).lower(): 
                or_pool.extend(vals)
            else: 
                skolitel_pool.extend(vals)
        return list(set(or_pool)), list(set(skolitel_pool))

    def generate_schedule(self):
        or_pool, skolitel_pool = self._parse_pools()
        or_idx, skolitel_idx = 0, 0
        busy_map = {}

        def get_free_person(pool, current_idx, day, time_str, exclude_set):
            if not pool: return "CHYBÍ LIDI", current_idx
            attempts = 0
            while attempts < len(pool):
                person = pool[current_idx % len(pool)]
                current_idx += 1
                attempts += 1
                if person in exclude_set: continue
                if person in busy_map.get((day, time_str), set()): continue
                return person, current_idx
            return "KOLIZE (málo lidí)", current_idx

        self.students_df['Final_Milnik'] = self.students_df.apply(
            lambda r: str(r['M1_2_Volba']) if r['Milník'] == '1 nebo 2' else str(r['Milník']), axis=1
        )
        
        day1_df = self.students_df[self.students_df['Final_Milnik'].isin(['1', '3'])].copy()
        day2_df = self.students_df[self.students_df['Final_Milnik'].isin(['2', '4'])].copy()
        schedule = []

        def process_day(df_day, day_name):
            nonlocal or_idx, skolitel_idx
            students = df_day.to_dict('records')
            chunks = [students[i:i+10] for i in range(0, len(students), 10)]
            
            for k_idx, chunk in enumerate(chunks):
                komise_name = f"Komise {k_idx+1}"
                pref_predseda, or_idx = get_free_person(or_pool, or_idx, day_name, "ALL", set())
                pref_mistopredseda, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, "ALL", set())

                curr_t = datetime(2000, 1, 1, 8, 0)
                for student in chunk:
                    t_str = curr_t.strftime("%H:%M")
                    if (day_name, t_str) not in busy_map:
                        busy_map[(day_name, t_str)] = set()
                        
                    milnik = student['Final_Milnik']
                    skolitel = student['Školitel']
                    role = {c: "" for c in ["Předseda", "Místopředseda", "Člen 1", "Člen 2 / Externista", "Oponent 1", "Oponent 2", "Oponent 3"]}
                    
                    assigned_this_slot = set([skolitel])
                    busy_map[(day_name, t_str)].add(skolitel)
                    
                    if pref_predseda not in ["CHYBÍ LIDI", "KOLIZE (málo lidí)"] and pref_predseda not in assigned_this_slot and pref_predseda not in busy_map[(day_name, t_str)]:
                        p = pref_predseda
                    else:
                        p, or_idx = get_free_person(or_pool, or_idx, day_name, t_str, assigned_this_slot)
                    role["Předseda"] = p
                    assigned_this_slot.add(p); busy_map[(day_name, t_str)].add(p)
                    
                    if pref_mistopredseda not in ["CHYBÍ LIDI", "KOLIZE (málo lidí)"] and pref_mistopredseda not in assigned_this_slot and pref_mistopredseda not in busy_map[(day_name, t_str)]:
                        mp = pref_mistopredseda
                    else:
                        mp, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, t_str, assigned_this_slot)
                    role["Místopředseda"] = mp
                    assigned_this_slot.add(mp); busy_map[(day_name, t_str)].add(mp)

                    if milnik in ['1', '3']:
                        c1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, t_str, assigned_this_slot)
                        role["Člen 1"] = c1
                        assigned_this_slot.add(c1); busy_map[(day_name, t_str)].add(c1)
                        
                    elif milnik == '2':
                        c1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, t_str, assigned_this_slot)
                        role["Člen 1"] = c1
                        assigned_this_slot.add(c1); busy_map[(day_name, t_str)].add(c1)
                        
                        role["Člen 2 / Externista"] = "EXTERNISTA (RUČNĚ)"
                        
                        o1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, t_str, assigned_this_slot)
                        role["Oponent 1"] = f"{o1} (Interní)"
                        assigned_this_slot.add(o1); busy_map[(day_name, t_str)].add(o1)
                        
                    elif milnik == '4':
                        role["Oponent 1"] = "EXTERNISTA 1 (RUČNĚ)"
                        role["Oponent 2"] = "EXTERNISTA 2 (RUČNĚ)"
                        o3, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, t_str, assigned_this_slot)
                        role["Oponent 3"] = f"{o3} (Interní)"
                        assigned_this_slot.add(o3); busy_map[(day_name, t_str)].add(o3)

                    zaznam = {"Den": day_name, "Čas": t_str, "Komise": komise_name, "Student": student['Student'], "Milník": milnik, "Přítomen (Školitel)": skolitel}
                    zaznam.update(role)
                    schedule.append(zaznam)
                    curr_t += timedelta(minutes=45)

        process_day(day1_df, "Den 1")
        process_day(day2_df, "Den 2")
        
        self.schedule_df = pd.DataFrame(schedule)
        pool_data = [{"Jméno": j, "Role": "Oborová rada"} for j in or_pool]
        pool_data += [{"Jméno": j, "Role": "Školitel"} for j in skolitel_pool]
        self.pool_df = pd.DataFrame(pool_data)

# --- MODUL B: UŽIVATELSKÉ ROZHRANÍ (GUI) ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Generátor zkušebních komisí")
        self.resize(1300, 850)
        self.processor = DataProcessor()
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.stack = QStackedWidget()
        self.layout.addWidget(self.stack)
        
        self.screen_import, self.screen_generate, self.screen_edit = QWidget(), QWidget(), QWidget()
        self.setup_import_screen(); self.setup_generate_screen(); self.setup_edit_screen()
        self.stack.addWidget(self.screen_import); self.stack.addWidget(self.screen_generate); self.stack.addWidget(self.screen_edit)

    def setup_import_screen(self):
        layout = QVBoxLayout(self.screen_import)
        layout.addWidget(QLabel("<h2>1. Import a rozlišení milníků</h2>"))
        self.table_students = QTableWidget()
        layout.addWidget(self.table_students)
        btn_layout = QHBoxLayout()
        self.btn_load = QPushButton("Načíst data ze souborů")
        self.btn_load.clicked.connect(self.load_data_action)
        self.btn_to_gen = QPushButton("Pokračovat ke generování ->")
        self.btn_to_gen.setEnabled(False)
        self.btn_to_gen.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        btn_layout.addWidget(self.btn_load); btn_layout.addStretch(); btn_layout.addWidget(self.btn_to_gen)
        layout.addLayout(btn_layout)

    def load_data_action(self):
        if self.processor.load_and_process("DoctoralThesis_CZ.xls", "DoctoralThesis_EN.xls", "phd_komise.xlsx"):
            self.refresh_student_table()
            self.btn_to_gen.setEnabled(True)
        else:
            QMessageBox.critical(self, "Chyba", "Nepodařilo se načíst data.")

    def refresh_student_table(self):
        df = self.processor.students_df
        self.table_students.setRowCount(len(df)); self.table_students.setColumnCount(7)
        self.table_students.setHorizontalHeaderLabels(["Student", "Školitel", "Stav studia", "Stav DiP", "Milník", "Upřesnění", "Název práce"])
        for i, r in df.iterrows():
            self.table_students.setItem(i,0,QTableWidgetItem(str(r['Student'])))
            self.table_students.setItem(i,1,QTableWidgetItem(str(r['Školitel'])))
            self.table_students.setItem(i,2,QTableWidgetItem(str(r['Stav studijního poměru'])))
            self.table_students.setItem(i,3,QTableWidgetItem(str(r['Stav DiP'])))
            self.table_students.setItem(i,4,QTableWidgetItem(str(r['Milník'])))
            if r['Milník'] == "1 nebo 2":
                cb = QCheckBox("M2"); cb.stateChanged.connect(lambda s, idx=i: self.update_milestone_val(idx, s))
                self.table_students.setCellWidget(i, 5, cb)
            else:
                self.table_students.setItem(i, 5, QTableWidgetItem("-"))
            self.table_students.setItem(i,6,QTableWidgetItem(str(r['Název DiP - česky'])))
        self.table_students.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def update_milestone_val(self, idx, state): self.processor.students_df.at[idx, 'M1_2_Volba'] = "2" if state == 2 else "1"

    def setup_generate_screen(self):
        layout = QVBoxLayout(self.screen_generate)
        layout.addStretch(); lbl = QLabel("<h1>Algoritmus připraven</h1>"); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); layout.addWidget(lbl)
        btn = QPushButton("SPUSTIT GENEROVÁNÍ"); btn.setFixedSize(300,60); btn.clicked.connect(self.run_algorithm); layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter); layout.addStretch()

    def run_algorithm(self): 
        self.processor.generate_schedule()
        self.refresh_results_tables()
        self.stack.setCurrentIndex(2)

    def setup_edit_screen(self):
        layout = QVBoxLayout(self.screen_edit)
        layout.addWidget(QLabel("<h2>3. Finální harmonogram a ruční editace (Přetahujte jména z dolní části)</h2>"))
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        self.table_results = DraggableTableWidget()
        splitter.addWidget(self.table_results)
        
        pool_w = QWidget(); p_lay = QVBoxLayout(pool_w); p_lay.addWidget(QLabel("<b>Dostupní členové:</b>"))
        self.table_pool = DraggableTableWidget(); p_lay.addWidget(self.table_pool); splitter.addWidget(pool_w)
        
        layout.addWidget(splitter)
        
        btn_lay = QHBoxLayout()
        btn_check = QPushButton("Zkontrolovat složení a časové konflikty")
        btn_check.setStyleSheet("background-color: #d1f2eb; font-weight: bold;")
        btn_check.clicked.connect(self.validate_schedule)
        
        btn_export = QPushButton("💾 Exportovat do Excelu")
        btn_export.setStyleSheet("background-color: #d4e6f1; font-weight: bold;")
        btn_export.clicked.connect(self.export_to_excel)
        
        btn_reset = QPushButton("Zpět (Reset)")
        btn_reset.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        
        btn_lay.addWidget(btn_check)
        btn_lay.addWidget(btn_export)
        btn_lay.addStretch()
        btn_lay.addWidget(btn_reset)
        layout.addLayout(btn_lay)

    def refresh_results_tables(self):
        df = self.processor.schedule_df
        if not df.empty:
            # OPRAVA: Propojení databázových názvů se zkrácenými UI názvy
            df_cols = ["Den", "Čas", "Komise", "Student", "Milník", "Předseda", "Místopředseda", "Člen 1", "Člen 2 / Externista", "Oponent 1", "Oponent 2", "Oponent 3", "Přítomen (Školitel)"]
            ui_headers = ["Den", "Čas", "Komise", "Student", "M", "Předseda", "Místopředseda", "Člen 1", "Člen 2 / Externista", "Oponent 1", "Oponent 2", "Oponent 3", "Školitel"]
            
            self.table_results.setRowCount(len(df)); self.table_results.setColumnCount(len(ui_headers))
            self.table_results.setHorizontalHeaderLabels(ui_headers)
            
            for i, r in df.iterrows():
                for j, col in enumerate(df_cols):
                    val = r.get(col, "")
                    item = QTableWidgetItem(str(val))
                    if col == "Předseda" and val: 
                        item.setBackground(QColor("#e6f2ff")); item.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                    self.table_results.setItem(i, j, item)
            self.table_results.resizeColumnsToContents()

        df_p = self.processor.pool_df
        if not df_p.empty:
            self.table_pool.setRowCount(len(df_p)); self.table_pool.setColumnCount(2)
            self.table_pool.setHorizontalHeaderLabels(["Jméno", "Role"])
            for i, r in df_p.iterrows():
                n_it = QTableWidgetItem(str(r['Jméno'])); r_it = QTableWidgetItem(str(r['Role']))
                if r['Role'] == "Oborová rada": 
                    n_it.setBackground(QColor("#e6f2ff")); n_it.setFont(QFont("Arial", 9, QFont.Weight.Bold))
                self.table_pool.setItem(i, 0, n_it); self.table_pool.setItem(i, 1, r_it)
            self.table_pool.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    
    def validate_schedule(self):
        conflicts = []; missing = []; presence_map = {} 
        or_members = set(self.processor.pool_df[self.processor.pool_df['Role'] == 'Oborová rada']['Jméno'].astype(str).str.strip())

        for row in range(self.table_results.rowCount()):
            # Reset barev
            for col in range(self.table_results.columnCount()):
                item = self.table_results.item(row, col)
                if item: item.setBackground(QColor("white") if col != 5 else QColor("#e6f2ff"))

            den = self.table_results.item(row, 0).text()
            cas = self.table_results.item(row, 1).text()
            mistnost = self.table_results.item(row, 2).text()
            student = self.table_results.item(row, 3).text()
            milnik = self.table_results.item(row, 4).text()
            skolitel = self.table_results.item(row, 12).text()
            
            seen_in_this_commission = set()
            has_or_member = False

            for col in range(5, 12):
                item = self.table_results.item(row, col)
                if not item: continue
                jmeno = item.text().strip()
                
                if not jmeno or "RUČNĚ" in jmeno.upper() or "KOLIZE" in jmeno.upper() or "CHYBÍ" in jmeno.upper(): continue
                if jmeno in or_members: has_or_member = True
                
                if jmeno == skolitel:
                    conflicts.append(f"Student {student}: {jmeno} je školitel! Nesmí být členem komise.")
                    item.setBackground(QColor("#f5b7b1")) 
                if jmeno in seen_in_this_commission:
                    conflicts.append(f"Duplicita: {jmeno} je ve stejné komisi ({mistnost}, {cas}) vícekrát!")
                    item.setBackground(QColor("#f5b7b1")) 
                else: seen_in_this_commission.add(jmeno)

                key = (den, cas, jmeno)
                if key in presence_map:
                    if mistnost not in presence_map[key]:
                        presence_map[key].append(mistnost)
                        conflicts.append(f"Časový překryv: {jmeno} je v čase {cas} ({den}) v místnostech: {presence_map[key]}")
                        item.setBackground(QColor("#f5b7b1")) 
                else: presence_map[key] = [mistnost]

            if not has_or_member:
                missing.append(f"Student {student}: V komisi chybí alespoň jeden zástupce Oborové rady!")
                p_item = self.table_results.item(row, 5)
                if p_item: p_item.setBackground(QColor("#fad7a1"))

            # Kontrola podle ročníku
            mandatory_indices = {"1": [5, 6, 7], "3": [5, 6, 7], "2": [5, 6, 7, 8, 9], "4": [5, 6, 9, 10, 11]}
            
            # OPRAVA 1: Bezpečné čtení čísla milníku
            m_key = milnik.replace("M", "").strip() 
            
            if m_key in mandatory_indices:
                for idx in mandatory_indices[m_key]:
                    item = self.table_results.item(row, idx)
                    text = item.text().strip() if item else ""
                    
                    # OPRAVA 2: Rozlišení mezi skutečnou chybou a zástupným textem
                    if not text or "KOLIZE" in text.upper():
                        missing.append(f"Student {student}: Chybí obsazení ({self.table_results.horizontalHeaderItem(idx).text()})")
                        if item: item.setBackground(QColor("#fcf3cf")) # Žlutá (Skutečná chyba)
                    elif "RUČNĚ" in text.upper():
                        # Není to chyba, jen zástupný text. Obarvíme neutrální šedou.
                        if item: item.setBackground(QColor("#eaeded")) # Šedá (Jen info)

        if not conflicts and not missing: 
            QMessageBox.information(self, "Validace OK", "Excelentní! Harmonogram nemá žádné konflikty.\n\nZástupné texty pro externisty jsou podbarveny šedě a připraveny na tvé ruční doplnění.")
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

if __name__ == "__main__":
    app = QApplication(sys.argv); win = MainWindow(); win.show(); sys.exit(app.exec())