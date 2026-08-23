/* ============================= DATA ============================= */

const CHECKLIST1 = [
  {id:"vitalparameter", title:"Vitalparameter erfassen", fields:[
    {key:"vital_rr_sys", label:"RR systolisch (mmHg)", type:"number", min:0},
    {key:"vital_rr_dia", label:"RR diastolisch (mmHg)", type:"number", min:0},
    {key:"vital_puls", label:"Puls (/min)", type:"number", min:0},
    {key:"vital_spo2", label:"SpO2 (%)", type:"number", min:0, max:100},
    {key:"vital_temp", label:"Temperatur (C)", type:"number", step:"0.1"},
    {key:"vital_gewicht", label:"Gewicht (kg)", type:"number", min:0, step:"0.1"}
  ]},

  {divider:"Fragebögen"},
  {id:"fb-g8", title:"Fragebogen G8 (geriatrisches Screening)", detail:["Bei tiefem Score: Zuweisung ad Geriatrie"], fields:[
    {key:"score_g8", label:"G8-Score (0–17)", type:"number", min:0, max:17},
    {key:"g8_zuweisung", label:"Zuweisung Geriatrie", type:"select", options:["Ja","Nein"]}
  ]},
  {id:"fb-nrs", title:"Fragebogen NRS (Nutritional Risk Screening)", flagRule:"ernaehrung", fields:[
    {key:"score_nrs", label:"NRS-Score (0–7)", type:"number", min:0, max:7}
  ]},
  {id:"fb-ecog", title:"Fragebogen ECOG", fields:[
    {key:"score_ecog", label:"ECOG Performance Status", type:"select", options:[
      "0 = vollständig aktiv",
      "1 = körperlich anstrengende Aktivität eingeschränkt",
      "2 = gehfähig, aber zunehmend eingeschränkt",
      "3 = überwiegend Bett/Stuhl",
      "4 = vollständig pflegeabhängig",
      "5 = verstorben"
    ]}
  ]},
  {id:"fb-stopbang", title:"Fragebogen STOP-BANG", flagRule:"pneumo", fields:[
    {key:"score_stopbang", label:"Anzahl Ja-Antworten (0–8)", type:"number", min:0, max:8}
  ]},
  {id:"fb-epworth", title:"Epworth Sleepiness Scale", flagRule:"pneumo", fields:[
    {key:"score_epworth", label:"Epworth-Score (0–24)", type:"number", min:0, max:24}
  ]},
  {id:"fb-mmrc", title:"mMRC Dyspnoeskala", flagRule:"kardio", fields:[
    {key:"score_mmrc", label:"mMRC-Grad", type:"select", options:["0","1","2","3","4"]}
  ]},

  {divider:"Labor (inkl. PBM)"},
  {id:"laborwerte", title:"Laborwerte erfassen", custom:"labs"},

  {divider:"Zuweisungen &amp; Massnahmen"},
  {id:"anaesthesie", title:"Anmeldung Anästhesie-Sprechstunde (PAB)", fields:[
    {key:"anaesthesie_termin", label:"Termin-Datum", type:"date"}
  ]},
  {id:"pbm", title:"Einleitung PBM gemäss Weisung „Perioperative Therapie von Anämie und Eisenmangel“", detail:[
    "Weisung: <a href='https://portal.ksw.ch/dep/ana/GelenkteDokumente/PBM%20Perioperative%20Therapie%20von%20Ana%CC%88mie%20und%20Eisenmangel%20Standard.docx?Web=1' target='_blank' rel='noopener'>PBM-Standard (KSW-Portal)</a>",
    "Details werden nach fachlicher Klärung gemäss Weisung ergänzt."
  ], fields:[
    {key:"pbm_status", label:"Status", type:"select", options:["Noch zu prüfen","Eingeleitet","Nicht notwendig"]},
    {key:"pbm_ansprechperson", label:"Ansprechperson / Notiz", type:"text"}
  ]},
  {id:"kardio", title:"Überprüfung Zuweisung Kardiologie gemäss Weisung „Präoperative kardiale Abklärung“", detail:[
    "Zuweisung sobald Kriterien erfüllt, oder vorbekannt EF &lt;50% oder mMRC Grad 3/4"
  ], flagRule:"kardio", fields:[
    {key:"kardio_ef", label:"EF (%)", type:"number", min:0, max:100},
    {key:"kardio_mmrs", label:"mMRS", type:"number", min:0, max:6}
  ]},
  {id:"raucher", title:"Raucheranamnese", fields:[
    {key:"raucher_status", label:"Status", type:"select", options:["Nieraucher","Ex-Raucher, sistiert >1 Jahr","Ex-Raucher, sistiert <1 Jahr","Aktiver Raucher"]},
    {key:"raucher_menge", label:"Zigaretten/Tag", type:"number", min:0},
    {key:"raucher_py", label:"Pack Years", type:"number", min:0, step:"0.1"},
    {key:"raucher_sistiert_seit", label:"Sistiert seit (MM/JJJJ)", type:"text", placeholder:"MM/JJJJ"}
  ], detail:[
    "Nieraucher: keine Massnahmen",
    "Ex-Raucher &gt;1 Jahr sistiert: Anbindung Rauchstopp-Sprechstunde bei Wunsch",
    "Raucher oder sistiert &lt;1 Jahr: Anbindung Rauchstopp-Sprechstunde via KISIM „Anmeldung Pneumologie Sprechstunde“ → „Rauchstopp“"
  ]},
  {id:"sucht", title:"Suchtmittelanamnese", fields:[
    {key:"sucht_alkohol", label:"Alkohol – was, wie häufig?", type:"text"}
  ], custom:"suchtmittel"},
  {id:"pneumo-osas", title:"Zuweisung Pneumologie – OSAS-Abklärung", flagRule:"pneumo", fields:[
    {key:"pneumo_niv", label:"Bekanntes (O)SAS mit NIV-Therapie?", type:"select", options:["Ja","Nein"]}
  ], detail:[
    "Bei bekanntem NIV: Patient instruieren, OSAS-Gerät mitzubringen",
    "Zuweisung wenn STOP-BANG ≥3× Ja oder Epworth ≥11 — via KISIM „Anmeldung Pneumologie Sprechstunde“"
  ]},
  {id:"pneumo-copd", title:"Zuweisung Pneumologie – COPD / Asthma / Lungenfibrose / neuromuskulär", fields:[
    {key:"pneumo_grunderkrankung", label:"Grunderkrankung", type:"select", options:["Keine","COPD","Asthma","Lungenfibrose/restriktive Lungenfunktion","Neuromuskuläre Erkrankung/Tetraplegie"]},
    {key:"pneumo_letzte_kontrolle", label:"Letzte Kontrolle Pneumologie", type:"date"},
    {key:"pneumo_verschlechterung", label:"Verschlechterung?", type:"select", options:["Ja","Nein"]}
  ], detail:[
    "COPD ab Gold I UND Kontrolle &gt;1 Jahr ODER Verschlechterung",
    "Asthma symptomatisch/Verschlechterung ODER Kontrolle &gt;1 Jahr",
    "Restriktive Lungenfunktion/Fibrose: Kontrolle &gt;6 Monate → Anmeldung via KISIM „Lungenfunktion (LuFu)“"
  ]},
  {id:"ernaehrung1", title:"Anmeldung Ernährungsberatung", flagRule:"ernaehrung", fields:[
    {key:"ernaehrung_termin", label:"Termin vereinbart am", type:"date"}
  ], detail:[
    "Zuweisung wenn NRS ≥3 (siehe Fragebögen)",
    "Via KISIM Anmeldung „Ernährungstherapie/-beratung ambulant“ — Aufgebot innert 2 Wochen"
  ]},
  {id:"physio1", title:"Anmeldung Physiotherapie", fields:[
    {key:"physio_neoblase", label:"Neoblase geplant?", type:"select", options:["Ja","Nein"]},
    {key:"physio_rehakur", label:"Reha/Kur bereits geplant?", type:"select", options:["Ja","Nein","Noch offen"]}
  ], detail:[
    "Alle Patient*innen: Anmeldung „Vita-Reha“ präoperativ via KISIM",
    "Falls Neoblase: zusätzlich „Beckenbodenphysiotherapie“",
    "Falls keine Reha/Kur geplant: zusätzlich „Vita-Reha“ postoperativ"
  ]},
  {id:"diagnosen", title:"Vervollständigung Diagnosenliste"},
  {id:"medikamente", title:"Vervollständigung Medikamentenliste"},
  {id:"kisimpfad", title:"KISIM-Pfad verordnen"},
  {id:"postopmgmt", title:"Postoperatives Management besprechen", fields:[
    {key:"postop_wahl", label:"Gewählte Nachsorge", type:"select", options:["Reha","Kur","Nach Hause mit Spitex"]}
  ], detail:[
    "Reha → Kostengutsprache: „Arztzeugnis Nachsorge / Nachsorge- und Sozialberatung“, an Operateur zur Signatur",
    "Nach Hause mit Spitex → Mitteilung an Pflege: „bitte um Organisation Spitex nach Austritt“"
  ]},
  {id:"thromboinfo", title:"Patient über Thromboseprophylaxe informieren", fields:[
    {key:"thrombo_plan", label:"Plan / Verordnung", type:"text"},
    {key:"thrombo_eGFR", label:"eGFR (ml/min), falls relevant", type:"text"}
  ], detail:[
    "Bei eGFR &lt;15 ml/min: Rücksprache mit Operateur",
    "Wenn bereits unter OAK/Marcoumar: nicht notwendig"
  ]},
  {id:"operateurtermin", title:"Termin beim Operateur 10–14 Tage vor Operation vorhanden?", fields:[
    {key:"operateur_termin_status", label:"Termin vorhanden?", type:"select", options:["Ja","Nein"]},
    {key:"operateur_termin_datum", label:"Termin-Datum", type:"date"}
  ]},
  {id:"drink", title:"Information hochkalorischer Drink", detail:[
    "Am Vorabend der Operation: 400 ml (4×100 ml) — Ausnahme: Diabetiker*innen nicht",
    "Am Morgen, spätestens 2h präoperativ: 200 ml (2×100 ml)",
    "Abgabe und Instruktion am BENE-Termin"
  ]},
  {id:"urinkultur1", title:"Planung Urinkultur", fields:[
    {key:"urinkultur_datum", label:"Geplantes Datum", type:"date"}
  ]}
];

const PHASES = [
  {
    id:"praeop", tag:"Phase 1", title:"Präoperativ",
    roles:[
      {id:"p-uro", title:"Urologie-Konsultation", note:"wenn möglich beim Operateur", items:[
        {title:"OP-Aufklärung"},
        {title:"OP-Anmeldung", detail:["In Rücksprache mit Operateur"]},
        {title:"BENE-Nurse informieren", detail:["Per Telefon oder Mail informieren und Termin vereinbaren"], fields:[
          {key:"bene_termin_datum", label:"Termin vereinbart am", type:"date"}
        ]},
        {title:"Tumorboard (bei onkologischer Zystektomie)", fields:[
          {key:"onko_tumorboard_datum", label:"Tumorboard-Datum", type:"date"}
        ]},
        {title:"Anmeldung Onkologie (bei onkologischer Zystektomie)", fields:[
          {key:"onko_chemo", label:"Periop. Chemoimmuntherapie geplant?", type:"select", options:["Ja","Nein"]},
          {key:"onko_behandler", label:"Zuständige/r Onkologe/in", type:"text"}
        ]},
        {title:"Erneute Sprechstunde Urologie (10–14 Tage vor Zystektomie)", fields:[
          {key:"onko_folgetermin_datum", label:"Termin-Datum", type:"date"}
        ]}
      ]},
      {id:"p-bene", title:"BENE/ERAS-Sprechstunde", note:"siehe Tab „Prä-OP Checkliste“", jump:true, items:[]},
      {id:"p-anaes", title:"Anästhesiologie", items:[
        {title:"Checkliste / SOP Anästhesie Zystektomie durchführen"}
      ]},
      {id:"p-physio", title:"Physiotherapie", note:"Anmeldung via BENE-Nurse", items:[
        {title:"Prä- und postoperative Vita-Reha"},
        {title:"Kostengutsprache", detail:["Wird durch Physiotherapie gestellt — bei Ablehnung kontaktiert Physiotherapie den behandelnden Arzt"]},
        {title:"Beckenboden bei Neoblase"},
        {title:"Präop Vita-Reha vs. einmalige Konsultation", detail:["Möglich 6–12 Wochen vor OP"], fields:[
          {key:"physio_pathway_praeop", label:"Gewählt", type:"select", options:["Vita-Reha (Serie)","Einmalige Konsultation"]}
        ]}
      ]},
      {id:"p-ernaehr", title:"Ernährungsberatung", note:"Anmeldung via BENE-Nurse", items:[
        {title:"Kann auch telemedizinisch durchgeführt werden"},
        {title:"Optimierung Ernährung bei Malnutrition", detail:["Messung via NRS","Intervention ab NRS &gt;3","Kostengutsprache für präoperatives Fresubin / Ernährungsoptimierung"]},
        {title:"Keine Rezepte für High-Carb-Produkte"}
      ]},
      {id:"p-stoma", title:"Stomaberatung", note:"Anmeldung via BENE-Nurse", items:[
        {title:"Zeitpunkt und Anzahl Treffen individuell festlegen", fields:[
          {key:"stoma_anzahl_treffen", label:"Anzahl Treffen", type:"select", options:["1","2"]}
        ]},
        {title:"Fakultatives Treffen bei Unsicherheit bezüglich Stoma"}
      ]}
    ]
  },
  {
    id:"intraop", tag:"Phase 2", title:"Intraoperativ",
    roles:[
      {id:"i-uro", title:"Urologisch-operativ", items:[{title:"Antibiotische Prophylaxe"}]},
      {id:"i-anaes", title:"Anästhesie", items:[{title:"Checkliste / SOP Anästhesie Zystektomie durchführen"}]},
      {id:"i-lager", title:"Lagerungspflege", items:[{title:"SCDs immer", detail:["Wird durch Melanie Gaudin in der Anmeldung hinterlegt"]}]}
    ]
  },
  {
    id:"postop-stat", tag:"Phase 3", title:"Postoperativ stationär",
    roles:[
      {id:"s-pflege", title:"Pflege", note:"Meilensteine je Tag", items:[
        {title:"OP-Tag", detail:["Neben dem Bett gestanden / am Bettrand gesessen","Fresubin / klare Flüssigkeit wird vertragen","Kaugummi und Kaffee sobald genug wach","Schmerzen mit entsprechender Medikation tolerierbar"]},
        {title:"1. postoperativer Tag", detail:["4h ausserhalb des Bettes / 24h","Vollkost wird toleriert","Patient trägt eigene Kleidung","Schmerzen mit entsprechender Medikation tolerierbar"]},
        {title:"2. postoperativer Tag", detail:["Instruktion Fragmin-Injektion erfolgt","4 Ganglängen gelaufen","6h ausserhalb des Bettes / 24h","Schmerzen mit entsprechender Medikation tolerierbar"]},
        {title:"Ab 3. postoperativem Tag", detail:["Fortschritte beim Gehtraining","Bei Neoblase: Instruktion „Blase anspülen“ erfolgt","Kann Urinbeutel selbständig leeren","Am Wochenende übernimmt Pflege die AktAss-Aufgaben gemäss Physio-Schema"]},
        {title:"Dokumentation", detail:["Alles Obige in KISIM ärztlich oder pflegerisch (siehe Beispiel Pflegeprozess BENE Pankreas)"]}
      ]},
      {id:"s-physio", title:"Physiotherapie", items:[
        {title:"Ab 1. postoperativem Tag Frühmobilisation mit Aktivitätsassistent"},
        {title:"Physiotherapie ggf. bereits 1. POD, sonst 1–2× während Aufenthalt"},
        {title:"Aktivitätsassistenz täglich"},
        {title:"Mindestziele gemäss Plan Physiotherapie", detail:[
          "OP-Tag: Bettrand / kurze Strecke im Zimmer",
          "PO1 (evtl. +1): selbständig zimmermobil / ½ bis ganze Ganglänge in Begleitung",
          "PO2 (evtl. +1): ½ bis ganze Ganglänge selbständig / mehrere Ganglängen &amp; Treppe in Begleitung",
          "PO3 (evtl. +1): selbständiges Gehtraining / MTT &amp; Treppentraining mit AktAss",
          "Am Wochenende keine AktAss → Übernahme durch Pflege"
        ]},
        {title:"Dokumentation erwünscht"}
      ]},
      {id:"s-ernaehr", title:"Ernährungsberatung", items:[
        {title:"Kostaufbau", detail:["Tag 1–3: Vollkost ¼ Portion","Besuch am 3. POD, dann Steigerung auf ½ Portion","Ziel: Vollkost ab 1. Tag"]},
        {title:"Wunschkost", detail:["Kann nur verordnet werden, wenn Ernährungsberatung involviert ist"]}
      ]},
      {id:"s-stoma", title:"Stomaberatung", items:[{title:"Besuch während stationärem Aufenthalt"}]},
      {id:"s-uro-visite", title:"Ärztlich Urologie — Visite &amp; Labor", items:[
        {title:"Visitendokumentation gemäss Vorlage"},
        {title:"Labortermine", detail:[
          "1. POD: Hb, K, Na, Kreatinin, Troponin",
          "2. POD: Hb, K, Na, Kreatinin, Mg, Troponin",
          "3. POD: Hb, Na, K, Kreatinin, Mg, CRP",
          "4. POD: Hb, Na, K, Kreatinin, Mg, CRP",
          "Danach gemäss Operateur — Lactatanstieg im Rahmen der Operation ist zu erwarten"
        ]},
        {title:"Troponin-Kontrolle (V.a. periop. Myokardinfarkt)", flagRule:"tropo", detail:[
          "Anstieg Troponin T hs &gt;14 ng/L Tag 1/2 vs. präOP-Wert; ohne präOP-Wert: &gt;70 ng/L oder An-/Abstieg &gt;14 ng/L Tag1 vs. Tag2",
          "Konsequenz: EKG und Konsil Kardiologie"
        ], fields:[
          {key:"tropo_preop", label:"Troponin präOP (ng/L)", type:"number"},
          {key:"tropo_tag1", label:"Troponin Tag 1 (ng/L)", type:"number"},
          {key:"tropo_tag2", label:"Troponin Tag 2 (ng/L)", type:"number"}
        ]},
        {title:"Transfusionsgrenze 90 g/L", detail:["Bei geplanter Transfusion ab höheren Werten: Rücksprache mit Operateur (negativer Einfluss auf Onkologie)"]},
        {title:"Kaliumziel hochnormal 4–4.5 mmol/L", detail:["Sobald Kalium &lt;4 mmol/L: Start ≥60 mmol/24h Kalium i.v. bis Koststufe 2"]}
      ]},
      {id:"s-uro-mikro", title:"Ärztlich Urologie — Mikrobiologie &amp; Thromboseprophylaxe", items:[
        {title:"Urinkultur aus Stomabeutel am 4. POD"},
        {title:"Clexane", detail:["Start am OP-Tag 6h postoperativ, danach täglich (im KISIM inkl. Dosierung)","Insgesamt 4 Wochen postoperativ","Instruktion bis 2. POD erfolgt"]},
        {title:"Intermittierende pneumatische Kompression (SCD-Pumpe)", detail:["Solange auf IPS, danach Wechsel auf Thrombosestrümpfe bis Austritt"]}
      ]},
      {id:"s-uro-analgesie", title:"Ärztlich Urologie — Analgesie &amp; Kost", items:[
        {title:"Rectus-Sheath-Katheter gemäss SOP"},
        {title:"PDA-Katheter", detail:["Ca. 72h postoperativ gemäss Anästhesie"]},
        {title:"Basisanalgesie i.v. oder p.o.", detail:["Novalgin, Dafalgan, NSAR","Wenn immer möglich keine Opiate — NRS 3/10 akzeptieren, erst bei ausgeschöpfter Basisanalgesie"]},
        {title:"Kost- und Medikamentenplan", detail:[
          "Freie Flüssigkeit schluckweise am OP-Tag, Kaugummi/Kaffee sobald wach",
          "Vollkost ab 1. postoperativem Tag; Magnesiocard 5 mmol 1-0-0-0 p.o.; Kalium gemäss Labor",
          "Pantoprazol 40 mg i.v., ab 2. POD p.o. bis Austritt",
          "Freka Klyss durch Arzt am 2. POD wenn noch kein Stuhlgang; medikamentöse Darmstimulation",
          "Tägliche Gewichtsmessung, Bilanz immer, Bilanzziel ± 0 ml",
          "Keine reguläre antibiotische Prophylaxe"
        ]}
      ]},
      {id:"s-uro-drain", title:"Ärztlich Urologie — Drainagen &amp; Urostoma", items:[
        {title:"Ureterkatheter beidseits", detail:["Links mit schräger Spitze — Fördermenge kontrollieren, bei Bedarf anspülen mit 2–4 ml, 1×/Schicht"]},
        {title:"Urostoma-Management", detail:[
          "Urinkultur aus Stomabeutel am 3. POD",
          "Bei Austritt am 5. POD: Entfernung UK rechts am 5. und UK links am 6. POD unter resistenzgerechter Therapie oder Bactrim p.o.",
          "Bei früherem Austritt: Entfernung nach 7–14 Tagen beim Operateur — Sonographie, resistenzgerecht oder empirisch 1× Bactrim p.o. bei negativer Urinkultur"
        ], fields:[
          {key:"urostoma_entfernung_re", label:"Entfernung UK rechts (Datum)", type:"date"},
          {key:"urostoma_entfernung_li", label:"Entfernung UK links (Datum)", type:"date"}
        ]}
      ]},
      {id:"s-uro-austritt", title:"Ärztlich Urologie — Austrittsbericht", items:[
        {title:"Diagnosen überprüfen (CW-relevant)", detail:[
          "Postoperatives Delir",
          "Akute Nephritis mit Keimen (a.e. Pyelonephritis nach Zug Mono-J-Katheter)",
          "Karzinom als Hauptdiagnose",
          "Blutungsanämie mit Massnahmen / Suche nach Blutungsquelle",
          "Alle Erreger dokumentieren"
        ]}
      ]},
      {id:"s-ips", title:"Ärztlich IPS", items:[
        {title:"MAP mindestens 65 mmHg halten"},
        {title:"Volumenplus vermeiden", detail:["Grosszügig Vasopressoren nutzen (reduziert Komplikationen um ca. 50%, Wuethrich et al., Anesthesiology 2014)","Erhöhung der Volumengabe nur nach Rücksprache mit Oberarzt IPS oder Operateur"]}
      ]},
      {id:"s-schmerz", title:"Ärztlich Anästhesie / Schmerzdienst", items:[
        {title:"Bei PDA: Laufrate nach Schmerzen anpassen", detail:["Nicht zu früh reduzieren nur zur Blutdruckoptimierung"]}
      ]}
    ]
  },
  {
    id:"postop-amb", tag:"Phase 4", title:"Postoperativ ambulant",
    roles:[
      {id:"a-aerztlich", title:"Ärztlich", items:[
        {title:"Thromboseprophylaxe für 4 Wochen postoperativ fortführen"},
        {title:"Bei Ileum-Conduit", detail:["Bei Austritt am 5. POD: Entfernung UK nach 7–14 Tagen beim Operateur — Sonographie, resistenzgerecht oder empirisch 1× Bactrim p.o. bei negativer Urinkultur"], fields:[
          {key:"amb_ileum_uk_entfernung", label:"Entfernung UK (Datum)", type:"date"}
        ]},
        {title:"Bei Neoblase", detail:[
          "Urinkultur aus Pouchkatheter (Hausarzt oder Urologie)",
          "Re-Hospitalisation für 1 Nacht zur Inbetriebnahme der Neoblase, unter resistenzgerechter Therapie gemäss Kultur",
          "Zystographie, vBGA vor Katheterzug und am Morgen danach"
        ], fields:[
          {key:"amb_neoblase_rehosp_datum", label:"Re-Hospitalisation (Datum)", type:"date"}
        ]}
      ]},
      {id:"a-physio", title:"Physiotherapie", items:[
        {title:"Vita-Reha analog präoperativ, falls keine Reha geplant"},
        {title:"Booklet analog präoperativ"},
        {title:"Bei Neoblase: postoperativ Beckenboden"}
      ]},
      {id:"a-stoma", title:"Stomaberatung", items:[
        {title:"Termine postoperativ festlegen", fields:[
          {key:"amb_stoma_termin", label:"Termin-Datum", type:"date"}
        ]}
      ]},
      {id:"a-ernaehr", title:"Ernährungsberatung", items:[{title:"Nach Hospitalisation aktuell nicht vorgesehen"}]}
    ]
  }
];

/* Rules for auto-computed flags, keyed by data-rule name.
   Multiple flag-boxes across the app can share the same rule. */
const FLAG_RULES = {
  pneumo: (a) => {
    const sb = parseFloat(a["score_stopbang"]);
    const ep = parseFloat(a["score_epworth"]);
    if ((!isNaN(sb) && sb >= 3) || (!isNaN(ep) && ep >= 11)) {
      return "STOP-BANG ≥3 oder Epworth ≥11 → Zuweisung Pneumologie zur OSAS-Abklärung empfohlen.";
    }
    return null;
  },
  ernaehrung: (a) => {
    const nrs = parseFloat(a["score_nrs"]);
    if (!isNaN(nrs) && nrs >= 3) return "NRS ≥3 → Zuweisung Ernährungsberatung empfohlen.";
    return null;
  },
  kardio: (a) => {
    const ef = parseFloat(a["kardio_ef"]);
    const mmrc = parseFloat(a["score_mmrc"]);
    const mmrs = parseFloat(a["kardio_mmrs"]);
    if ((!isNaN(ef) && ef < 50) || (!isNaN(mmrc) && mmrc >= 3) || (!isNaN(mmrs) && mmrs >= 3)) {
      return "EF <50%, mMRC Grad 3/4 oder mMRS ≥3 → Zuweisung Kardiologie empfohlen.";
    }
    return null;
  },
  tropo: (a) => {
    const pre = parseFloat(a["tropo_preop"]);
    const t1 = parseFloat(a["tropo_tag1"]);
    const t2 = parseFloat(a["tropo_tag2"]);
    let trigger = false;
    if (!isNaN(pre)) {
      if ((!isNaN(t1) && (t1 - pre) > 14) || (!isNaN(t2) && (t2 - pre) > 14)) trigger = true;
    } else {
      if ((!isNaN(t1) && t1 > 70) || (!isNaN(t2) && t2 > 70) || (!isNaN(t1) && !isNaN(t2) && Math.abs(t1 - t2) > 14)) trigger = true;
    }
    return trigger ? "V.a. periop. Myokardinfarkt → EKG und Konsil Kardiologie veranlassen." : null;
  }
};

/* ============================= STATE ============================= */
const LAB_OPTIONS = [
  "Hb", "Leukozyten", "Thrombozyten", "Quick / INR", "Ferritin", "Transferrinsättigung",
  "Kreatinin", "Natrium", "Kalium", "CRP", "Troponin T", "BNP", "Albumin", "Anderer Wert"
];

let STATE = { patientName:"", opDate:"", checked:{}, openBlocks:{}, answers:{}, notes:{}, labs:[], suchtmittel:[] };
let saveTimer = null;

function esc(s){
  return String(s == null ? "" : s).replace(/&/g,"&amp;").replace(/"/g,"&quot;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

function preopItemIds(){
  return CHECKLIST1.filter(i=>!i.divider).map(i => "t1:"+i.id);
}

function pathItemIds(){
  const ids = [];
  PHASES.forEach(ph => ph.roles.forEach(r => r.items.forEach((it,idx) => ids.push("t2:"+r.id+":"+idx))));
  return ids;
}

function allItemIds(){
  return preopItemIds().concat(pathItemIds());
}

function fieldsHTML(fields){
  return `<div class="fields">${fields.map(f=>{
    const val = STATE.answers[f.key];
    if (f.type === "select"){
      const opts = ['<option value="">–</option>'].concat(
        f.options.map(o => `<option value="${esc(o)}" ${val===o?"selected":""}>${esc(o)}</option>`)
      );
      return `<label class="field"><span>${esc(f.label)}</span><select data-fkey="${f.key}">${opts.join("")}</select></label>`;
    }
    const minAttr = f.min!==undefined ? ` min="${f.min}"` : "";
    const maxAttr = f.max!==undefined ? ` max="${f.max}"` : "";
    const stepAttr = f.step!==undefined ? ` step="${f.step}"` : "";
    return `<label class="field"><span>${esc(f.label)}</span><input type="${f.type}" data-fkey="${f.key}" value="${esc(val||"")}" placeholder="${esc(f.placeholder||"")}"${minAttr}${maxAttr}${stepAttr}></label>`;
  }).join("")}</div>`;
}

function optionsHTML(options, val){
  return ['<option value="">–</option>'].concat(
    options.map(o => `<option value="${esc(o)}" ${val===o?"selected":""}>${esc(o)}</option>`)
  ).join("");
}

function labRowsHTML(){
  const rows = STATE.labs && STATE.labs.length ? STATE.labs : [{type:"", value:"", unit:""}];
  STATE.labs = rows;
  return `<div class="dynamic-list" data-dynamic="labs">
    ${rows.map((row, idx) => `<div class="dynamic-row">
      <label class="field"><span>Laborwert</span><select data-lab-idx="${idx}" data-lab-key="type">${optionsHTML(LAB_OPTIONS, row.type)}</select></label>
      <label class="field"><span>Wert</span><input type="text" data-lab-idx="${idx}" data-lab-key="value" value="${esc(row.value||"")}"></label>
      <label class="field"><span>Einheit</span><input type="text" data-lab-idx="${idx}" data-lab-key="unit" value="${esc(row.unit||"")}" placeholder="z.B. g/L"></label>
      <button type="button" class="icon-btn" data-remove-lab="${idx}" aria-label="Laborwert entfernen">×</button>
    </div>`).join("")}
    <button type="button" class="add-row-btn" data-add-lab>+ Laborwert hinzufügen</button>
  </div>`;
}

function suchtRowsHTML(){
  const rows = STATE.suchtmittel && STATE.suchtmittel.length ? STATE.suchtmittel : [{substance:"", frequency:""}];
  STATE.suchtmittel = rows;
  return `<div class="dynamic-list" data-dynamic="suchtmittel">
    ${rows.map((row, idx) => `<div class="dynamic-row">
      <label class="field"><span>Droge / Substanz</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="substance" value="${esc(row.substance||"")}"></label>
      <label class="field"><span>Häufigkeit</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="frequency" value="${esc(row.frequency||"")}" placeholder="z.B. täglich"></label>
      <label class="field"><span>Bemerkung</span><input type="text" data-sucht-idx="${idx}" data-sucht-key="note" value="${esc(row.note||"")}"></label>
      <button type="button" class="icon-btn" data-remove-sucht="${idx}" aria-label="Droge entfernen">×</button>
    </div>`).join("")}
    <button type="button" class="add-row-btn" data-add-sucht>+ Droge hinzufügen</button>
  </div>`;
}

function customHTML(kind){
  if (kind === "labs") return labRowsHTML();
  if (kind === "suchtmittel") return suchtRowsHTML();
  return "";
}

function itemHTML(id, title, opts){
  opts = opts || {};
  const { detail, fields, flagRule, custom } = opts;
  const checked = !!STATE.checked[id];
  const detailHTML = detail ? `<div class="item-detail"><ul>${detail.map(d=>`<li>${d}</li>`).join("")}</ul></div>` : "";
  const fieldsStr = fields && fields.length ? fieldsHTML(fields) : "";
  const customStr = custom ? customHTML(custom) : "";
  const flagHTML = flagRule ? `<div class="flag-box" data-rule="${flagRule}"></div>` : "";
  const noteVal = STATE.notes[id] || "";
  const noteOpen = noteVal ? "open" : "";
  return `<div class="item ${checked?'checked':''}" data-id="${id}">
    <input type="checkbox" ${checked?'checked':''} data-id="${id}">
    <div class="item-body">
      <div class="item-title" data-id="${id}">${title}</div>
      ${detailHTML}
      ${fieldsStr}
      ${customStr}
      ${flagHTML}
      <button type="button" class="note-toggle" data-notetoggle="${id}">${noteVal? '– Notiz ausblenden' : '+ Notiz'}</button>
      <div class="note-wrap ${noteOpen}" data-notewrap="${id}">
        <textarea data-notekey="${id}" rows="2" placeholder="Freitext-Notiz…">${esc(noteVal)}</textarea>
      </div>
    </div>
  </div>`;
}

function dividerHTML(label){
  return `<div class="group-divider">${label}</div>`;
}

function renderChecklist1(){
  const el = document.getElementById('items-t1');
  el.innerHTML = CHECKLIST1.map(i => i.divider ? dividerHTML(i.divider) : itemHTML("t1:"+i.id, i.title, i)).join("");
}

function renderPhases(){
  const container = document.getElementById('phases-t2');
  container.innerHTML = PHASES.map(ph => {
    const rolesHTML = ph.roles.map(r => {
      const isOpen = STATE.openBlocks[r.id] !== false; // default open
      let itemsHTML;
      if (r.jump){
        itemsHTML = `<div style="padding:6px 0 4px;">
          <div style="font-size:13px;color:var(--ink-soft);">Wird im Tab «Prä-OP Checkliste» separat abgehakt.</div>
          <button class="jumplink" data-jump="t1">Zur Prä-OP Checkliste →</button>
        </div>`;
      } else {
        itemsHTML = r.items.map((it,idx) => itemHTML("t2:"+r.id+":"+idx, it.title, it)).join("");
      }
      const total = r.items.length;
      const done = r.items.reduce((n,it,idx)=> n + (STATE.checked["t2:"+r.id+":"+idx] ? 1:0), 0);
      const countLabel = r.jump ? "" : `<span class="role-count">${done}/${total}</span>`;
      return `<div class="role-block ${isOpen?'open':''}" data-role="${r.id}">
        <div class="role-head" data-role-toggle="${r.id}">
          <span class="chev">▸</span>
          <span class="role-title">${r.title}${r.note?`<span style="font-weight:400;color:var(--ink-soft);"> — ${r.note}</span>`:''}</span>
          ${countLabel}
        </div>
        <div class="role-items">${itemsHTML}</div>
      </div>`;
    }).join("");

    const totalItems = ph.roles.reduce((n,r)=> n + r.items.length, 0);
    const doneItems = ph.roles.reduce((n,r)=> n + r.items.reduce((m,it,idx)=> m + (STATE.checked["t2:"+r.id+":"+idx]?1:0),0), 0);

    return `<div class="phase-head">
        <span class="phase-tag">${ph.tag}</span>
        <h2>${ph.title}</h2>
        <span class="phase-progress">${doneItems}/${totalItems}</span>
      </div>
      ${rolesHTML}`;
  }).join("");
}

function scrollToChecklistTarget(tab, selector){
  switchTab(tab);
  window.requestAnimationFrame(() => {
    const target = document.querySelector(selector);
    if (!target) return;

    const roleBlock = target.closest('.role-block');
    if (roleBlock){
      roleBlock.classList.add('open');
      STATE.openBlocks[roleBlock.dataset.role] = true;
      scheduleSave();
    }

    target.scrollIntoView({behavior:'smooth', block:'start'});
  });
}

function attachHandlers(){
  document.body.addEventListener('click', (e) => {
    const cb = e.target.closest('input[type=checkbox]');
    if (cb && cb.dataset.id){
      STATE.checked[cb.dataset.id] = cb.checked;
      scheduleSave();
      updateProgress();
      const row = cb.closest('.item');
      if (row) row.classList.toggle('checked', cb.checked);
      const roleBlock = cb.closest('.role-block');
      if (roleBlock) refreshRoleCount(roleBlock.dataset.role);
      return;
    }
    const titleEl = e.target.closest('.item-title');
    if (titleEl && titleEl.dataset.id){
      const box = document.querySelector(`input[type=checkbox][data-id="${titleEl.dataset.id}"]`);
      if (box){ box.checked = !box.checked; box.dispatchEvent(new Event('click', {bubbles:true})); }
      return;
    }
    const roleToggle = e.target.closest('[data-role-toggle]');
    if (roleToggle){
      const id = roleToggle.dataset.roleToggle;
      const block = roleToggle.closest('.role-block');
      block.classList.toggle('open');
      STATE.openBlocks[id] = block.classList.contains('open');
      scheduleSave();
      return;
    }
    const jump = e.target.closest('[data-jump]');
    if (jump){
      switchTab(jump.dataset.jump);
      return;
    }
    const addLab = e.target.closest('[data-add-lab]');
    if (addLab){
      STATE.labs.push({type:"", value:"", unit:""});
      renderChecklist1();
      updateFlags();
      scheduleSave();
      return;
    }
    const removeLab = e.target.closest('[data-remove-lab]');
    if (removeLab){
      const idx = parseInt(removeLab.dataset.removeLab, 10);
      STATE.labs.splice(idx, 1);
      if (!STATE.labs.length) STATE.labs.push({type:"", value:"", unit:""});
      renderChecklist1();
      updateFlags();
      scheduleSave();
      return;
    }
    const addSucht = e.target.closest('[data-add-sucht]');
    if (addSucht){
      STATE.suchtmittel.push({substance:"", frequency:"", note:""});
      renderChecklist1();
      updateFlags();
      scheduleSave();
      return;
    }
    const removeSucht = e.target.closest('[data-remove-sucht]');
    if (removeSucht){
      const idx = parseInt(removeSucht.dataset.removeSucht, 10);
      STATE.suchtmittel.splice(idx, 1);
      if (!STATE.suchtmittel.length) STATE.suchtmittel.push({substance:"", frequency:"", note:""});
      renderChecklist1();
      updateFlags();
      scheduleSave();
      return;
    }
    const nt = e.target.closest('[data-notetoggle]');
    if (nt){
      const id = nt.dataset.notetoggle;
      const wrap = document.querySelector(`[data-notewrap="${id}"]`);
      wrap.classList.toggle('open');
      nt.textContent = wrap.classList.contains('open') ? '– Notiz ausblenden' : '+ Notiz';
      if (wrap.classList.contains('open')){
        const ta = wrap.querySelector('textarea');
        if (ta) ta.focus();
      }
      return;
    }
  });

  document.querySelectorAll('[data-rail-target]').forEach(btn => {
    btn.addEventListener('click', () => {
      scrollToChecklistTarget(btn.dataset.railTab, btn.dataset.railTarget);
    });
  });

  document.body.addEventListener('input', (e) => {
    const f = e.target.closest('[data-fkey]');
    if (f){
      STATE.answers[f.dataset.fkey] = f.value;
      scheduleSave();
      updateFlags();
      return;
    }
    const lab = e.target.closest('[data-lab-idx]');
    if (lab){
      const idx = parseInt(lab.dataset.labIdx, 10);
      STATE.labs[idx][lab.dataset.labKey] = lab.value;
      scheduleSave();
      return;
    }
    const sucht = e.target.closest('[data-sucht-idx]');
    if (sucht){
      const idx = parseInt(sucht.dataset.suchtIdx, 10);
      STATE.suchtmittel[idx][sucht.dataset.suchtKey] = sucht.value;
      scheduleSave();
      return;
    }
    const n = e.target.closest('[data-notekey]');
    if (n){
      STATE.notes[n.dataset.notekey] = n.value;
      scheduleSave();
      return;
    }
  });

  document.body.addEventListener('change', (e) => {
    const f = e.target.closest('select[data-fkey]');
    if (f){
      STATE.answers[f.dataset.fkey] = f.value;
      scheduleSave();
      updateFlags();
    }
    const lab = e.target.closest('select[data-lab-idx]');
    if (lab){
      const idx = parseInt(lab.dataset.labIdx, 10);
      STATE.labs[idx][lab.dataset.labKey] = lab.value;
      scheduleSave();
    }
  });

  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => switchTab(btn.dataset.tab));
  });

  document.getElementById('pname').addEventListener('input', e => { STATE.patientName = e.target.value; scheduleSave(); });
  document.getElementById('opdate').addEventListener('input', e => { STATE.opDate = e.target.value; scheduleSave(); });

  document.getElementById('printBtn').addEventListener('click', () => window.print());
  document.getElementById('resetBtn').addEventListener('click', () => {
    if (confirm('Wirklich zurücksetzen? Alle Häkchen, Eingaben und Notizen dieser Checkliste werden gelöscht.')){
      STATE = { patientName:"", opDate:"", checked:{}, openBlocks:{}, answers:{}, notes:{}, labs:[], suchtmittel:[] };
      document.getElementById('pname').value = "";
      document.getElementById('opdate').value = "";
      renderChecklist1();
      renderPhases();
      updateProgress();
      updateFlags();
      saveState(true);
    }
  });
}

function refreshRoleCount(roleId){
  const ph = PHASES.find(p => p.roles.some(r=>r.id===roleId));
  if (!ph) return;
  const r = ph.roles.find(rr=>rr.id===roleId);
  if (!r || r.jump) return;
  const block = document.querySelector(`.role-block[data-role="${roleId}"] .role-count`);
  if (block){
    const total = r.items.length;
    const done = r.items.reduce((n,it,idx)=> n + (STATE.checked["t2:"+r.id+":"+idx] ? 1:0), 0);
    block.textContent = `${done}/${total}`;
  }
  const phaseHead = document.querySelectorAll('.phase-head .phase-progress');
  const idx = PHASES.findIndex(p=>p.id===ph.id);
  if (phaseHead[idx]){
    const totalItems = ph.roles.reduce((n,rr)=> n + rr.items.length, 0);
    const doneItems = ph.roles.reduce((n,rr)=> n + rr.items.reduce((m,it,i2)=> m + (STATE.checked["t2:"+rr.id+":"+i2]?1:0),0), 0);
    phaseHead[idx].textContent = `${doneItems}/${totalItems}`;
  }
}

function switchTab(tab){
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab===tab));
  document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
  document.getElementById('panel-'+tab).classList.add('active');
}

function updateProgress(){
  renderProgress(preopItemIds(), 'preopPct', 'preopSegbar');
  renderProgress(pathItemIds(), 'pathPct', 'pathSegbar');
}

function renderProgress(ids, pctId, segId){
  const total = ids.length;
  const done = ids.filter(id => STATE.checked[id]).length;
  const pct = total ? Math.round((done/total)*100) : 0;
  document.getElementById(pctId).textContent = pct + '%';
  const segCount = 20;
  const filled = Math.round((pct/100)*segCount);
  const seg = document.getElementById(segId);
  seg.innerHTML = Array.from({length:segCount}).map((_,i)=> `<div class="seg ${i<filled?'filled':''}"></div>`).join("");
}

function updateFlags(){
  Object.keys(FLAG_RULES).forEach(rule => {
    const text = FLAG_RULES[rule](STATE.answers);
    document.querySelectorAll(`.flag-box[data-rule="${rule}"]`).forEach(el => {
      if (text){ el.textContent = text; el.classList.add('show'); }
      else { el.textContent = ''; el.classList.remove('show'); }
    });
  });
}

function scheduleSave(){
  clearTimeout(saveTimer);
  document.getElementById('saveState').textContent = 'speichere …';
  saveTimer = setTimeout(() => saveState(false), 500);
}

async function saveState(){
  try{
    await window.storage.set('bene-eras-state-v3', JSON.stringify(STATE), false);
    document.getElementById('saveState').textContent = 'Automatisch gespeichert · ' + new Date().toLocaleTimeString('de-CH',{hour:'2-digit',minute:'2-digit'});
  }catch(err){
    document.getElementById('saveState').textContent = 'Speichern fehlgeschlagen — bitte Eingaben notieren';
    console.error('Storage error', err);
  }
}

async function loadState(){
  try{
    const res = await window.storage.get('bene-eras-state-v3', false);
    if (res && res.value){
      const parsed = JSON.parse(res.value);
      STATE = Object.assign({ patientName:"", opDate:"", checked:{}, openBlocks:{}, answers:{}, notes:{}, labs:[], suchtmittel:[] }, parsed);
    }
  }catch(err){
    // no saved state yet — start fresh
  }
  const params = new URLSearchParams(window.location.search);
  const patient = params.get("patient");
  const caseNumber = params.get("case");
  const opDate = params.get("opdate");
  if (patient || caseNumber){
    STATE.patientName = [patient, caseNumber ? `Fall ${caseNumber}` : ""].filter(Boolean).join(" · ");
  }
  if (opDate){
    STATE.opDate = opDate;
  }
  document.getElementById('pname').value = STATE.patientName || "";
  document.getElementById('opdate').value = STATE.opDate || "";
  renderChecklist1();
  renderPhases();
  updateProgress();
  updateFlags();
  document.getElementById('saveState').textContent = 'Bereit';
}

attachHandlers();
loadState();
