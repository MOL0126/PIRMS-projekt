# Generátor zkušebních komisí PIRMS

Tento software slouží k automatizovanému plánování harmonogramu doktorských zkoušek a generování složení zkušebních komisí[cite: 1]. Aplikace inteligentně zpracovává data o studentech, hlídá akademické standardy pro jednotlivé milníky (M1–M4) a zabraňuje časovým kolizím členů komisí[cite: 1, 2].

## Hlavní funkce

*   **Automatický import**: Načítání a čištění dat z českých i anglických Excelových exportů a seznamů komisí[cite: 1].
*   **Inteligentní klastrování**: Algoritmus seskupuje studenty podle školitelů, aby se minimalizoval počet komisí a přechodů mezi místnostmi[cite: 1].
*   **Filtrování dostupnosti**: Možnost manuálně vyřadit členy oborové rady nebo školitele, kteří nejsou v termínu zkoušek k dispozici[cite: 2].
*   **Interaktivní editor**: Podpora funkcí **Drag & Drop** pro snadné přesuny členů mezi komisemi a dedikovaný "Oponent mód"[cite: 2].
*   **Validace v reálném čase**: Systém automaticky kontroluje složení komisí podle typu milníku a hlídá časové překryvy členů[cite: 2].
*   **Export**: Finální harmonogram lze uložit do formátu `.xlsx` pro další distribuci[cite: 2].

## Technické požadavky

Aplikace je postavena na jazyce **Python 3.x** a využívá následující knihovny[cite: 1, 2]:
*   **pandas** & **openpyxl** – pro pokročilé zpracování dat a Excelových tabulek[cite: 1].
*   **PyQt6** – pro moderní grafické uživatelské rozhraní[cite: 2].

## Struktura projektu

| Soubor | Popis |
| :--- | :--- |
| `main.py` | Vstupní bod aplikace, inicializuje okno a spouští program[cite: 3]. |
| `gui.py` | Kompletní definice uživatelského rozhraní, správa obrazovek a interakcí[cite: 2]. |
| `data_processor.py` | Výpočetní jádro: algoritmus generování, výpočet délek zkoušek a validace[cite: 1]. |
| `.gitignore` | Konfigurace pro Git zajišťující čistotu repozitáře (ignoruje `venv`, `__pycache__` atd.). |

---

## Návod k použití

### 1. Příprava dat
Aplikace očekává v kořenové složce tyto soubory se specifickou strukturou[cite: 1]:
*   `DoctoralThesis_CZ.xls` a `DoctoralThesis_EN.xls`: Exporty ze studijního systému.
*   `phd_komise.xlsx`: Seznam členů oborové rady a školitelů rozdělený do listů.

### 2. Import a milníky
Po spuštění klikněte na **"Načíst data"**. Systém automaticky rozpozná milník studenta podle stavu jeho práce[cite: 1]:
*   **M1 / M2**: Teze zadány.
*   **M3**: DiP k zadání.
*   **M4**: DiP zadána.

### 3. Generování a úpravy
Algoritmus vypočítá harmonogram. V editačním okně můžete[cite: 2]:
*   Přetahovat jména ze seznamu dostupných členů přímo do tabulky.
*   Zapnout **Oponent mód** a kliknutím na jméno v komisi jej označit jako oponenta.

### 4. Validace
Před exportem vždy použijte tlačítko **"Zkontrolovat složení"**[cite: 2]. Algoritmus prověří logiku překryvů pomocí vzorce:

$$max(start_1, start_2) < min(end_1, end_2)$$

Pokud je podmínka splněna, dojde ke kolizi a systém vás upozorní[cite: 1, 2].

---

## Pravidla pro složení komisí

Aplikace striktně vymáhá následující akademická pravidla[cite: 1, 2]:

| Milník | Min. členů | Zástupce OR | Externisté | Oponenti |
| :--- | :---: | :---: | :---: | :---: |
| **M1 / M3** | 3 | Ano | Ne | Ne |
| **M2** | 5 | Ano | Min. 1 | Min. 1 |
| **M4** | 5 | Ano | Min. 2 | Min. 3 |

---
**Autor:** [MOL0126]
**Verze:** 2.0.0 (Stabilní)
