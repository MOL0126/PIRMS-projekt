import pandas as pd
import logging
import itertools
from datetime import datetime, timedelta

# --- KONFIGURACE LOGOVÁNÍ ---
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def get_duration(milnik):
    """Vrací délku zkoušky v minutách podle milníku."""
    m = str(milnik).replace("M", "").strip()
    if m == '1': return 30
    if m in ['2', '3']: return 45
    if m == '4': return 60
    return 45 # Default

def check_overlap(start1, end1, start2, end2):
    """Zkontroluje, zda se dva časové intervaly překrývají."""
    return max(start1, start2) < min(end1, end2)

class DataProcessor:
    def __init__(self):
        self.students_df = pd.DataFrame()
        self.komise_df = dict()
        self.schedule_df = pd.DataFrame()
        self.pool_df = pd.DataFrame()
        
        self.full_or_pool = []
        self.full_skolitel_pool = []
        self.active_or_pool = []
        self.active_skolitel_pool = []

    def load_and_process(self, cz_file_path, en_file_path, komise_file_path):
        try:
            df_cz = pd.read_excel(cz_file_path, skiprows=10)
            df_en = pd.read_excel(en_file_path, skiprows=10)
            self.komise_df = pd.read_excel(komise_file_path, sheet_name=None, engine='openpyxl')
            df_all = pd.concat([df_cz, df_en], ignore_index=True)
            df_all.columns = df_all.columns.astype(str).str.strip()
            
            self._process_students(df_all)
            self._parse_pools_initial()
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
        df_filtered['Zkouska_Aktivni'] = True
        
        self.students_df = df_filtered.reset_index(drop=True)

    def _determine_milestone(self, stav_dip):
        stav = str(stav_dip).strip()
        if stav == "Teze zadány": return "1 nebo 2"
        if stav == "DiP k zadání": return "3"
        if stav == "DiP zadána": return "4"
        return "Nespecifikováno"

    def _parse_pools_initial(self):
        or_pool, skolitel_pool = [], []
        for sheet_name, df in self.komise_df.items():
            if df.empty: continue
            vals = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
            if 'rada' in str(sheet_name).lower() or 'oborov' in str(sheet_name).lower(): 
                or_pool.extend(vals)
            else: 
                skolitel_pool.extend(vals)
                
        self.full_or_pool = sorted(list(set(or_pool)))
        self.full_skolitel_pool = sorted(list(set(skolitel_pool)))
        
        self.active_or_pool = self.full_or_pool.copy()
        self.active_skolitel_pool = self.full_skolitel_pool.copy()

    def generate_schedule(self):
        or_pool = self.active_or_pool if self.active_or_pool else ["CHYBÍ OR"]
        skolitel_pool = self.active_skolitel_pool if self.active_skolitel_pool else ["CHYBÍ ŠKOLITELÉ"]
        or_idx, skolitel_idx = 0, 0
        
        busy_map = {}

        def is_busy(person, day, s_dt, e_dt):
            return any(check_overlap(s_dt, e_dt, s, e) for s, e in busy_map.get((day, person), []))

        def get_free_person(pool, current_idx, day, start_dt, end_dt, exclude_set):
            if not pool: return "CHYBÍ LIDI", current_idx
            attempts = 0
            while attempts < len(pool):
                person = pool[current_idx % len(pool)]
                current_idx += 1
                attempts += 1
                if person in exclude_set: continue
                if is_busy(person, day, start_dt, end_dt): continue
                return person, current_idx
            return "KOLIZE (málo lidí)", current_idx

        def get_base_person(pool, current_idx):
            if not pool: return "", current_idx
            p = pool[current_idx % len(pool)]
            return p, current_idx + 1

        self.students_df['Final_Milnik'] = self.students_df.apply(
            lambda r: str(r['M1_2_Volba']) if r['Milník'] == '1 nebo 2' else str(r['Milník']), axis=1
        )
        
        active_students = self.students_df[self.students_df['Zkouska_Aktivni'] == True].copy()
        
        day1_df = active_students[active_students['Final_Milnik'].isin(['1', '3'])].copy()
        day2_df = active_students[active_students['Final_Milnik'].isin(['2', '4'])].copy()
        schedule = []

        def process_day(df_day, day_name):
            nonlocal or_idx, skolitel_idx
            
            skolitel_groups = {}
            for _, r in df_day.iterrows():
                skolitel_groups.setdefault(r['Školitel'], []).append(r.to_dict())
                
            clusters = sorted(skolitel_groups.values(), key=len, reverse=True)
            
            commissions = [[], [], []]
            for cluster in clusters:
                smallest = min(commissions, key=len)
                smallest.extend(cluster)
            
            for k_idx, chunk in enumerate(commissions):
                if not chunk: continue 
                komise_name = f"Komise {k_idx+1}"

                skolitel_counts = {}
                for student in chunk:
                    sk_name = student['Školitel']
                    if sk_name in skolitel_pool: 
                        skolitel_counts[sk_name] = skolitel_counts.get(sk_name, 0) + 1
                
                dominant = sorted(skolitel_counts.keys(), key=lambda k: skolitel_counts[k], reverse=True)
                
                base_team_set = set()
                base_p, or_idx = get_base_person(or_pool, or_idx)
                
                def get_unique_base(dom_idx):
                    nonlocal skolitel_idx
                    if dom_idx < len(dominant):
                        return dominant[dom_idx]
                    
                    attempts = 0
                    while attempts < len(skolitel_pool):
                        p, skolitel_idx = get_base_person(skolitel_pool, skolitel_idx)
                        attempts += 1
                        if p not in base_team_set and p not in dominant:
                            return p
                    return get_base_person(skolitel_pool, skolitel_idx)[0]
                
                base_mp = get_unique_base(0)
                base_team_set.add(base_mp)
                
                base_c1 = get_unique_base(1)
                base_team_set.add(base_c1)
                
                base_c2 = get_unique_base(2)
                base_team_set.add(base_c2)

                curr_t = datetime(2000, 1, 1, 8, 0)
                
                for student in chunk:
                    milnik = student['Final_Milnik']
                    m = str(milnik).replace("M", "").strip()
                    skolitel = student['Školitel']
                    
                    duration = get_duration(milnik)
                    end_t = curr_t + timedelta(minutes=duration)
                    t_str = curr_t.strftime("%H:%M")
                    
                    role = {c: "" for c in ["Předseda", "Místopředseda", "Člen 1", "Člen 2", "Člen 3", "Člen 4", "Člen 5"]}
                    assigned_this_slot = set([skolitel])
                    busy_map.setdefault((day_name, skolitel), []).append((curr_t, end_t))
                    
                    if base_p and base_p not in assigned_this_slot and not is_busy(base_p, day_name, curr_t, end_t):
                        p = base_p
                    else:
                        p, or_idx = get_free_person(or_pool, or_idx, day_name, curr_t, end_t, assigned_this_slot)
                    role["Předseda"] = p
                    assigned_this_slot.add(p); busy_map.setdefault((day_name, p), []).append((curr_t, end_t))
                    
                    if base_mp and base_mp not in assigned_this_slot and not is_busy(base_mp, day_name, curr_t, end_t):
                        mp = base_mp
                    else:
                        mp, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, curr_t, end_t, assigned_this_slot)
                    role["Místopředseda"] = mp
                    assigned_this_slot.add(mp); busy_map.setdefault((day_name, mp), []).append((curr_t, end_t))

                    if m in ['1', '3']:
                        if base_c1 and base_c1 not in assigned_this_slot and not is_busy(base_c1, day_name, curr_t, end_t):
                            c1 = base_c1
                        else:
                            c1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, curr_t, end_t, assigned_this_slot)
                        role["Člen 1"] = c1
                        assigned_this_slot.add(c1); busy_map.setdefault((day_name, c1), []).append((curr_t, end_t))
                        
                    elif m == '2':
                        if base_c1 and base_c1 not in assigned_this_slot and not is_busy(base_c1, day_name, curr_t, end_t):
                            c1 = base_c1
                        else:
                            c1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, curr_t, end_t, assigned_this_slot)
                        role["Člen 1"] = c1
                        assigned_this_slot.add(c1); busy_map.setdefault((day_name, c1), []).append((curr_t, end_t))
                        
                        if base_c2 and base_c2 not in assigned_this_slot and not is_busy(base_c2, day_name, curr_t, end_t):
                            c2 = base_c2
                        else:
                            c2, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, curr_t, end_t, assigned_this_slot)
                        role["Člen 2"] = c2
                        assigned_this_slot.add(c2); busy_map.setdefault((day_name, c2), []).append((curr_t, end_t))
                        
                        role["Člen 3"] = "EXTERNISTA (RUČNĚ)"
                        
                    elif m == '4':
                        if base_c1 and base_c1 not in assigned_this_slot and not is_busy(base_c1, day_name, curr_t, end_t):
                            c1 = base_c1
                        else:
                            c1, skolitel_idx = get_free_person(skolitel_pool, skolitel_idx, day_name, curr_t, end_t, assigned_this_slot)
                        role["Člen 1"] = c1
                        assigned_this_slot.add(c1); busy_map.setdefault((day_name, c1), []).append((curr_t, end_t))
                        
                        role["Člen 2"] = "EXTERNISTA 1 (RUČNĚ)"
                        role["Člen 3"] = "EXTERNISTA 2 (RUČNĚ)"

                    zaznam = {"Den": day_name, "Čas": t_str, "Komise": komise_name, "Student": student['Student'], "Milník": milnik, "Přítomen (Školitel)": skolitel}
                    zaznam.update(role)
                    schedule.append(zaznam)
                    
                    curr_t = end_t 

        process_day(day1_df, "Den 1")
        process_day(day2_df, "Den 2")
        
        self.schedule_df = pd.DataFrame(schedule)
        
        pool_data = [{"Jméno": j, "Role": "Oborová rada"} for j in or_pool]
        pool_data += [{"Jméno": j, "Role": "Školitel"} for j in skolitel_pool]
        self.pool_df = pd.DataFrame(pool_data)