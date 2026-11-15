# job-search-agent

Repo `job-search-agent` zawiera narzędzia oraz metodę poszukiwania pracy z pomocą agenta AI. Agent zbiera oferty, buduje CV pod ofertę, pisze wiadomość dla 1 oferty oraz zapisuje każdą wysyłkę w ledgerze. Repo zawiera także statystyki 1 poszukiwania pracy z okresu od 2026-09-21 do 2026-11-15.

[English version](README.en.md)

Legenda: MUSI oznacza wymóg. NIE WOLNO oznacza zakaz. MOŻE oznacza zezwolenie. Słowo „lub” oznacza co najmniej 1 człon. Słowo „albo” oznacza dokładnie 1 człon.

## Słownik

| Termin | Definicja | Słowa zakazane dla tego pojęcia |
|---|---|---|
| kandydat | Osoba, która szuka pracy i zatwierdza zasady wysyłki. | użytkownik, klient |
| agent | Program z modelem językowym, który wykonuje kroki metody: Claude Code albo Codex. | asystent, bot |
| profil | Plik JSON z danymi kandydata dla narzędzi, na wzór `examples/profile.example.json`. | konfiguracja, ustawienia |
| ledger | Plik JSON albo plik JSONL, który zapisuje każdą próbę wysyłki z datą oraz stanem. | rejestr, dziennik |
| trasa | Para: 1 pracodawca oraz 1 stanowisko. Ledger zapisuje trasę jako 1 klucz. | aplikacja |
| zgłoszenie unikalne | Pierwsza potwierdzona wysyłka CV na 1 trasę. | aplikacja |
| wysyłka ponowna | Każda późniejsza potwierdzona wysyłka CV na trasę, która ma zgłoszenie unikalne. | resend |
| odpowiedź | 1 wiadomość od osoby po stronie pracodawcy, zapisana w pliku zdarzeń. | odzew, reakcja |

Skróty: CBOP (Centralna Baza Ofert Pracy) oznacza portal ofert urzędów pracy. ATS (Applicant Tracking System) oznacza system rekrutacyjny pracodawcy. CAPTCHA oznacza test, który odróżnia człowieka od programu. RODO oznacza rozporządzenie UE 2016/679 o ochronie danych osobowych. SMTP oznacza protokół wysyłki poczty.

## Cel

Metoda skraca pracę przy zgłoszeniach i zachowuje 1 zgłoszenie dla 1 oferty. Agent wykonuje powtarzalne kroki. Kandydat ustala zasady, zatwierdza wysyłkę oraz rozwiązuje każdą CAPTCHA.

## Metoda

Agent wykonuje każdy krok w tej kolejności:

1. Zbieranie ofert: `tools/fetch_it_offers.py` pobiera oferty IT z justjoin.it oraz No Fluff Jobs. `tools/cbop_scan.py` pobiera oferty z CBOP.
2. Filtr: skrypt odrzuca ofertę poza miastem kandydata bez pracy zdalnej. Skrypt odrzuca też ofertę, której pensja jest mniejsza niż minimum z profilu.
3. Filtr ledgera: skrypt pomija ofertę, którą ledger już zawiera.
4. Kolejność: skrypt stawia oferty AI na początku listy, potem oferty od najnowszej.
5. CV pod ofertę: `tools/build_batch.py` buduje CV z wersji bazowej. CV dostaje nagłówek, profil oraz klauzulę RODO z nazwą administratora danych.
6. Wiadomość pod ofertę: agent pisze wiadomość dla 1 oferty. `tools/make_plan.py` odrzuca plan bez wiadomości, bez linków z profilu albo bez linku, który wskazuje 1 repo.
7. Wysyłka: agent wysyła e-mail albo wypełnia formularz w przeglądarce kandydata. Panel wysyłki e-mail leży w repo prywatnym.
8. Ledger: `tools/record.py` dopisuje wpis z datą, stanem, dowodem z ekranu oraz sumą SHA-256 pliku CV.
9. Poczta: agent przypisuje każdy wątek do etykiety: odpowiedź do napisania, odmowa, CV w bazie, potwierdzenie automatyczne albo odbicie. Narzędzie do kroku 9 leży w repo prywatnym; patrz sekcja „Do przeniesienia”.
10. Statystyki: `tools/stats.py` liczy zgłoszenia z ledgerów oraz odpowiedzi z pliku zdarzeń. Skrypt rysuje wykres SVG.

## Zasady

- Agentowi NIE WOLNO wysłać wiadomości, która wygląda jak masowa wysyłka. Każda wiadomość dotyczy 1 stanowiska.
- Każde CV MUSI kończyć się klauzulą RODO z nazwą oraz siedzibą administratora danych. Gdy oferta podaje własną klauzulę, agent wstawia klauzulę z oferty bez zmian.
- CAPTCHA zostaje przy człowieku. Gdy formularz pokaże CAPTCHA, agent zapisuje stan `filled-awaiting-owner` i zostawia kliknięcie kandydatowi.
- Agentowi NIE WOLNO zakładać kont na portalach rekrutacyjnych. Trasa, która wymaga konta, zostaje kandydatowi.
- Agent bierze fakty o kandydacie tylko z pliku faktów kandydata. Agentowi NIE WOLNO dopisać doświadczenia ani lat pracy.
- Ledger przechowuje każdą próbę, także próbę nieudaną. Agent sprawdza ledger przed każdą wysyłką, żeby uniknąć duplikatu.
- Dane osobowe zostają poza Git: profil, ledgery, CV oraz korespondencja leżą w katalogu prywatnym.

## Statystyki

![162 zgłoszenia dały 22 odpowiedzi i 1 zaproszenie na rozmowę](docs/stats.svg)

Liczby opisują stan na 2026-11-15, godz. 14:35. Plik [docs/stats.json](docs/stats.json) zawiera każdą liczbę z tej sekcji.

| Miara | Liczba |
|---|---|
| Zgłoszenia unikalne | 162 |
| Wysyłki ponowne | 80 |
| Wiadomości w istniejącym wątku poczty | 17 |
| Trasy bez potwierdzonej wysyłki | 13 |
| Odpowiedzi pracodawców | 22 |
| Odmowy | 16 |
| Informacje o zapisaniu CV w bazie | 3 |
| Inne odpowiedzi | 2 |
| Zaproszenia na rozmowę | 1 |

| Miesiąc | Zgłoszenia unikalne | Wysyłki ponowne | Odpowiedzi |
|---|---|---|---|
| 2026-09 | 2 | 0 | 0 |
| 2026-10 | 83 | 0 | 9 |
| 2026-11 | 77 | 80 | 13 |

| Kanał wysyłki | Zgłoszenia unikalne |
|---|---|
| e-mail przez SMTP | 102 |
| formularz pracuj.pl | 31 |
| inny formularz: ATS albo strona pracodawcy | 18 |
| formularz justjoin.it | 9 |
| formularz No Fluff Jobs | 2 |

| Typ oferty | Zgłoszenia unikalne |
|---|---|
| ogłoszenie na portalu albo na stronie pracodawcy | 96 |
| zgłoszenie z własnej inicjatywy, bez ogłoszenia | 58 |
| oferta z CBOP | 8 |

Przebieg w liczbach: we wrześniu 2026 agent wysłał 2 zgłoszenia e-mailem. W październiku 2026 agent wysłał 83 zgłoszenia, w tym 80 zgłoszeń 2026-10-02. W listopadzie 2026 agent wykonał 80 wysyłek ponownych. Agent wykonał 63 wysyłki ponowne 2026-11-03 z klauzulą RODO, której CV z października nie miały. Agent wykonał 17 wysyłek ponownych 2026-11-11 z CV z nowym profilem. Od 2026-11-09 agent wysyłał zgłoszenia także na oferty z CBOP. Od 2026-11-11 agent wybierał najpierw oferty AI.

Wniosek: 162 zgłoszenia unikalne dały 1 zaproszenie na rozmowę. Odmowy stanowią 16 z 22 odpowiedzi.

## Uruchomienie

Wymagania: Python 3 z biblioteką standardową. Skrypt `tools/build_cv.py` wymaga także pakietów `python-docx` oraz `pymupdf` oraz programu LibreOffice (`soffice`).

Sprawdzenie narzędzi bez danych prywatnych:

```sh
python3 -I tools/stats.py --demo
python3 -I tools/fetch_it_offers.py --demo
python3 -I tools/cbop_scan.py --demo
python3 -I tools/make_plan.py
python3 -I tools/record.py --demo
python3 -I tools/correct_cv.py --selftest
python3 -I tools/build_batch.py --demo
python3 -I tools/build_cv.py --demo
```

Wynik: każde polecenie wypisuje `ok`, `selftest ok` albo `demo OK`.

Praca na własnych danych. Wykonaj każdy krok w tej kolejności:

1. Utwórz katalog `private/` w katalogu repo. Plik `.gitignore` pomija katalog `private/`.
2. Skopiuj `examples/profile.example.json` do `private/profile.json` i wpisz własne dane.
3. Zapisz w `private/baselines/` wersję bazową CV w Markdown, na wzór dema w `tools/build_batch.py`.
4. Pobierz oferty poleceniem z bloku kodu A.
5. Wybierz oferty i zapisz plan zgłoszeń poleceniem z bloku kodu B.
6. Zbuduj CV poleceniem z bloku kodu C.
7. Po każdej wysyłce zapisz wpis w ledgerze poleceniem z bloku kodu D.
8. Policz statystyki poleceniem z bloku kodu E.

```sh
# A: offers
python3 -I tools/fetch_it_offers.py --profile private/profile.json --seen private/portal-submissions.jsonl > private/shortlist.jsonl
python3 -I tools/cbop_scan.py --profile private/profile.json --out private/cbop-candidates.json
# B: plan (specs, offer details and one message per offer are written by the agent)
python3 -I tools/make_plan.py private/profile.json private/specs.json private/details.json private/messages.json > private/plan.json
# C: CVs
python3 -I tools/build_batch.py --profile private/profile.json --plan private/plan.json --baselines private/baselines --out private/cv
# D: ledger entry
python3 -I tools/record.py --plan private/plan.json --cv-dir private/cv --ledger private/portal-submissions.jsonl \
  --profile private/profile.json it-ai-engineer-acme "Done! Your application has been sent"
# E: statistics (--submissions and --queue read the ledger and the queue of the e-mail panel, when you have one)
python3 -I tools/stats.py --portal private/portal-submissions.jsonl --outcomes private/outcomes.jsonl --out private/stats
```

Plik zdarzeń ma 1 odpowiedź w 1 wierszu: data, typ zdarzenia, odnośnik prywatny oraz źródło. Typ zdarzenia przyjmuje 1 z 4 wartości: `refusal`, `cv_filed`, `other_reply`, `interview_invitation`. Wzór zawiera `examples/outcomes.example.jsonl`.

## Do przeniesienia

Repo zawiera 8 narzędzi metody. Lista podaje 5 narzędzi, które zostały w repo prywatnym, oraz powód:

- panel wysyłki e-mail z ledgerem oraz kopiami wiadomości: kod zawiera konfigurację poczty kandydata;
- sortowanie poczty do etykiet: kod zawiera listę domen pracodawców oraz adres kandydata;
- pobieranie ofert z pracuj.pl oraz filtr tych ofert: kod zawiera ścieżki prywatne oraz reguły kandydata;
- budowa wierszy zgłoszeń z CBOP: kod zawiera dane ofert oraz treść wiadomości;
- sprawdzanie aktualności ofert oraz wyszukiwanie administratora danych w KRS: kod zawiera listę tras kandydata.

Każde narzędzie z listy wymaga przeniesienia danych do profilu oraz sprawdzianu `demo()`.

## Granice

- Repo nie wysyła wiadomości. Wysyłkę wykonuje panel prywatny albo kandydat.
- Statystyki opisują 1 poszukiwanie pracy. Statystyki nie opisują rynku pracy.
- Ledger zgłoszeń nie zapisuje odpowiedzi. Kandydat zapisuje odpowiedzi w pliku zdarzeń ręcznie.
- Liczba odpowiedzi pomija odmowy automatyczne z portali. Statystyki z 2026-11-15 nie liczą odmów automatycznych.
- Skrypt `fetch_it_offers.py` liczy pensję netto z brutto współczynnikiem 0,72. Wynik jest przybliżeniem dla filtra.
- Narzędzia działają z interfejsami API portali z 2026-11-15. Zmiana API portalu wymaga zmiany kodu.

## Licencja

Licencja MIT, plik [LICENSE](LICENSE).
