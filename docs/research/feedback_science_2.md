# GUSTAV Feedback Engine: Ein didaktisch fundiertes und technisch realisierbares Konzept


## Einleitung: Von der Feedback-Forschung zur technischen Implementierung

Die Entwicklung der Lernplattform GUSTAV steht vor einer zentralen Herausforderung, die sowohl pädagogischer als auch technischer Natur ist: die Skalierung von qualitativ hochwertigem, formativem Feedback. Die pädagogische Dringlichkeit dieses Vorhabens ist unbestritten. Die Forschung von Hattie, Shute und Narciss hat wiederholt gezeigt, dass wirksames Feedback zu den einflussreichsten Interventionen zur Steigerung von Lernleistungen zählt.<sup>1</sup> Es beantwortet die drei fundamentalen Fragen des Lernenden: "Wo stehe ich?" (Feed Up), "Wie geht es voran?" (Feedback) und "Wo geht es als Nächstes hin?" (Feed Forward). Die größte Hürde für die Umsetzung im Schulalltag ist der immense Zeitaufwand für Lehrkräfte. GUSTAV zielt darauf ab, diese Lücke durch künstliche Intelligenz zu schließen.

Dieses Ziel muss jedoch unter einer signifikanten technischen Einschränkung erreicht werden: dem Einsatz von relativ kleinen, lokal gehosteten Large Language Models (LLMs) mit etwa 8 Milliarden Parametern. Diese Entscheidung ist aus Gründen des Datenschutzes, der Kostenkontrolle und der Unabhängigkeit von externen Anbietern strategisch klug. Gleichzeitig limitiert sie die verfügbare Rechenleistung, die Komplexität der möglichen Inferenzketten und vor allem die Größe des Kontextfensters, also die Menge an Informationen, die das Modell gleichzeitig verarbeiten kann.<sup>5</sup> Die Qualität des generierten Feedbacks hängt somit in außergewöhnlichem Maße von einer intelligenten, effizienten und präzisen Bereitstellung von Kontext ab.

Dieses Dokument legt ein umfassendes, evidenzbasiertes Konzept für die Feedback-Engine von GUSTAV vor. Es navigiert gezielt im Spannungsfeld zwischen den hohen pädagogischen Idealen der Feedback-Forschung und den pragmatischen Realitäten kleiner, lokaler LLMs. Es dient dem Entwicklungsteam als strategische und technische Entscheidungsgrundlage für die Architektur und Implementierung eines Systems, das Lehrkräfte entlastet und Schülern einen echten, lernförderlichen Mehrwert bietet.


## A. Fundamentale Feedback-Strategie: Einmalig vs. Interaktiv

Die Wahl der grundlegenden Interaktionsform zwischen Schüler und KI – ein einmaliger, umfassender Bericht oder ein schrittweiser, dialogischer Prozess – ist eine der wichtigsten Architekturentscheidungen. Die optimale Strategie ist keine binäre Entscheidung, sondern eine kontextabhängige, die sich an der Art der Aufgabe und dem spezifischen Lernziel orientieren muss.


### 1. Pädagogische Vor- und Nachteile: Eine differenzierte Analyse

Die pädagogische Wirksamkeit von Feedback hängt stark von seiner Darreichungsform ab. Je nach Komplexität der Aufgabe und dem angestrebten Lernziel sind unterschiedliche Modi überlegen.

Der Fall für einmaliges (statisches) Feedback:

Für Aufgaben mit geringer intrinsischer kognitiver Last, wie Wissensabfragen (z.B. Vokabeltests, historische Daten), das Anwenden einfacher Formeln oder das Befolgen klar definierter Prozeduren, ist ein einmaliges, unmittelbares Feedback äußerst effektiv. Es erfüllt mehrere Schlüsselfunktionen:



* **Schnelle Korrektur:** Es korrigiert Fehlkonzeptionen, bevor sie sich im Gedächtnis verfestigen können. Studien belegen, dass Schüler, die unmittelbares Feedback erhalten, signifikant besser abschneiden als jene mit verzögertem oder keinem Feedback.<sup>8</sup>
* **Effizienz:** Der Prozess ist sowohl für den Schüler als auch für das System ressourcenschonend. Der Schüler erhält alle relevanten Informationen gebündelt und kann die Aufgabe abschließen.
* **Klarheit:** Bei geschlossenen Aufgaben mit einer klaren Richtig/Falsch-Dimension bietet ein statischer Bericht eine unmissverständliche Rückmeldung.

Dieses Vorgehen entspricht in Hattie & Timperleys Modell primär dem Feedback auf der Aufgabenebene (*task level*), das sich auf die Korrektheit der Lösung konzentriert (z.B. "Deine Antwort ist nicht korrekt. Das richtige Datum ist 1066, da die Schlacht von Hastings in diesem Jahr stattfand.").<sup>2</sup>

Der Fall für interaktives (dialogisches) Feedback:

Für komplexe, offene und schlecht definierte Aufgaben wie das Verfassen von Essays, das Entwickeln einer Argumentation, das Lösen mehrstufiger Probleme oder kreative Schreibprozesse ist ein interaktiver Ansatz pädagogisch weit überlegen. Er transformiert den Lernprozess von einer passiven Informationsaufnahme zu einer aktiven Auseinandersetzung.9 Die Vorteile sind vielfältig:



* **Förderung von Denkprozessen:** Anstatt eine fertige Korrektur zu präsentieren, kann die KI als sokratischer Tutor agieren. Sie stellt gezielte Fragen, die den Schüler zum Nachdenken anregen und ihn dabei unterstützen, eigene Lösungen zu entwickeln. Dies fördert kritisches Denken und Problemlösekompetenzen.<sup>9</sup>
* **Scaffolding und Prozessbegleitung:** Der Dialog ermöglicht es der KI, den Lernprozess zu begleiten und gezielte Hilfestellungen (Scaffolding) anzubieten, die genau auf den aktuellen Bedarf des Schülers zugeschnitten sind.<sup>11</sup> Das Feedback kann so von der reinen Aufgabenebene auf die Prozess- und Selbstregulationsebene gehoben werden ("Du hast eine klare These formuliert. Welche Belege aus dem Text könntest du nutzen, um dein zweites Argument zu untermauern?").<sup>2</sup>
* **Verbesserte Wissensverankerung:** Aktive Lernmethoden, zu denen ein interaktiver Feedback-Dialog zählt, führen nachweislich zu einer besseren und nachhaltigeren Wissensverankerung als passive Methoden wie das reine Lesen eines Berichts.<sup>12</sup>

Allerdings birgt der interaktive Ansatz eine subtile psychologische Herausforderung. Untersuchungen zeigen, dass Studierende in aktiven Lernumgebungen zwar objektiv mehr lernen, aber subjektiv das *Gefühl* haben, weniger zu lernen.<sup>12</sup> Dies liegt am höheren kognitiven Aufwand, der für die aktive Auseinandersetzung erforderlich ist. Während statisches Feedback passiv konsumiert wird, erfordert ein Dialog die Verarbeitung der KI-Rückmeldung, die Formulierung einer eigenen Antwort oder Überarbeitung und die erneute Interaktion. Dieser "produktive Kampf" kann fälschlicherweise als Zeichen für ineffektives Lernen interpretiert werden und zu Frustration führen. Für GUSTAV bedeutet dies, dass der interaktive Modus nicht nur eine simple Chat-Oberfläche sein darf. Die KI muss sorgfältig darauf ausgelegt sein, diesen kognitiven Aufwand zu managen, indem sie den Prozess transparent macht und den Schüler ermutigt, z.B. durch metakognitive Einwürfe wie: "Das ist eine anspruchsvolle Frage. Schritt für Schritt kommen wir der Lösung näher. Was wäre dein erster Gedanke dazu?".


### 2. Technische Implikationen eines interaktiven Ansatzes

Ein interaktiver Ansatz stellt deutlich höhere Anforderungen an die technische Architektur, insbesondere an die Datenhaltung im Supabase-Backend. Ein einfaches Speichern von Chat-Protokollen, wie es in vielen Conversational-AI-Anwendungen üblich ist <sup>14</sup>, ist hier unzureichend. Der Fokus muss auf der Nachverfolgung der Evolution der Schülerarbeit liegen, da das Feedback immer im Kontext einer spezifischen Version dieser Arbeit steht.

Die Datenbankarchitektur muss daher versionszentriert sein. Der Dreh- und Angelpunkt ist nicht die Konversation selbst, sondern die eingereichte Schülerlösung in ihren verschiedenen Fassungen. Eine einfache Verknüpfung von Nachrichten mit einem Benutzer würde den Bezug zur jeweiligen Arbeitsversion verlieren. Stattdessen muss die Datenbank in der Lage sein, den gesamten iterativen Prozess abzubilden: Ein Schüler reicht Version 1 ein, erhält dazu Feedback in einer Sitzung, überarbeitet seine Lösung und reicht Version 2 ein, was eine neue Feedback-Sitzung auslösen kann.

Eine robuste und skalierbare Datenbankstruktur in Supabase könnte wie folgt aussehen:



* **assignments**: Speichert die von der Lehrkraft erstellten Aufgaben.
    * assignment_id (PK), teacher_id, title, description, learning_materials_url, feedback_config (JSONB, speichert die Lehrereinstellungen aus Teil A.3 und B.2).
* **submissions**: Speichert jede einzelne Einreichung eines Schülers. Dies ist die zentrale Tabelle für die Versionierung.
    * submission_id (PK), student_id, assignment_id, version_number (Integer, z.B. 1, 2, 3), content (Text), submitted_at (Timestamp).
* **feedback_sessions**: Kapselt eine Interaktionssitzung, die sich auf eine bestimmte Einreichung bezieht.
    * session_id (PK), submission_id (FK zu submissions), started_at (Timestamp).
* **feedback_messages**: Speichert die einzelnen Nachrichten innerhalb einer Sitzung.
    * message_id (PK), session_id (FK zu feedback_sessions), parent_message_id (FK zu sich selbst, für Threading), sender_type (Enum: 'student', 'ai'), message_content (Text), timestamp.

Diese Struktur stellt sicher, dass jede Feedback-Nachricht eindeutig einer Sitzung und damit einer spezifischen Version der Schülerarbeit zugeordnet werden kann. Dies ermöglicht eine lückenlose Rekonstruktion des Lernprozesses für die Lehrkraft und liefert der KI den notwendigen historischen Kontext für nachfolgende Interaktionen.<sup>16</sup>


### 3. Klare Empfehlung und Konfiguration durch die Lehrkraft

GUSTAV sollte beide Modi – einmaliges und interaktives Feedback – unterstützen, um der Vielfalt pädagogischer Szenarien gerecht zu werden. Die Wahl des Modus sollte der Lehrkraft überlassen werden, da sie die Lernziele und die Eignung der Aufgabe am besten beurteilen kann. Die Konfiguration im Frontend muss dabei so einfach und intuitiv wie möglich gestaltet sein und sich an bewährten UI-Mustern für Lernmanagementsysteme (LMS) orientieren, die auf Klarheit und Reduzierung der kognitiven Last für die Lehrkraft abzielen.<sup>18</sup>

**UI/UX-Vorschlag für die Aufgabenkonfiguration:**

Im Einstellungsbereich für eine neue Aufgabe sollte die Lehrkraft eine klare, nicht-technische Wahlmöglichkeit erhalten:



---
**Feedback-Modus für GUSTAV-KI**

Wählen Sie, wie Schüler Feedback zu dieser Aufgabe erhalten sollen.

🔘 **Einmaliger Bericht**

Der Schüler reicht seine Arbeit einmal ein und erhält einen vollständigen Feedback-Bericht. Ideal für Wissensüberprüfungen, Tests oder finale Abgaben.

🔘 **Interaktiver Dialog**

Der Schüler kann in einen Dialog mit der KI treten, um seine Arbeit schrittweise zu verbessern. Ideal für Entwürfe, kreatives Schreiben und komplexe Problemlösungen.



---
Diese einfache Konfiguration ermöglicht es der Lehrkraft, mit einem Klick die pädagogisch passende Feedback-Strategie für die jeweilige Aufgabe festzulegen.

Die folgende Tabelle fasst die Analyse zusammen und dient als Entscheidungshilfe für die Implementierung.

**Tabelle A.1: Vergleich der Feedback-Modalitäten**


<table>
  <tr>
   <td>Kriterium
   </td>
   <td>Einmaliges (Statisches) Feedback
   </td>
   <td>Interaktives (Dialogisches) Feedback
   </td>
  </tr>
  <tr>
   <td><strong>Pädagogisches Ziel</strong>
   </td>
   <td>Schnelle Korrektur, Wissenssicherung, summative Bewertungsvorbereitung
   </td>
   <td>Prozessbegleitung, Förderung von Denkprozessen, Selbstregulation, formative Entwicklung
   </td>
  </tr>
  <tr>
   <td><strong>Typische Aufgabentypen</strong>
   </td>
   <td>Wissensabfragen, Rechenaufgaben, Lückentexte, definierte Prozeduren
   </td>
   <td>Essay-Entwürfe, Argumentationsanalysen, kreatives Schreiben, komplexe Problemlösungen
   </td>
  </tr>
  <tr>
   <td><strong>Kognitive Belastung (Schüler)</strong>
   </td>
   <td>Gering; passive Aufnahme eines Berichts
   </td>
   <td>Hoch; erfordert aktive Verarbeitung, Reflexion und Reaktion
   </td>
  </tr>
  <tr>
   <td><strong>Schüler-Engagement</strong>
   </td>
   <td>Gering bis mittel; reaktiv
   </td>
   <td>Hoch; aktiv und partizipativ
   </td>
  </tr>
  <tr>
   <td><strong>Umgang mit Fehlkonzeptionen</strong>
   </td>
   <td>Korrigiert das Endergebnis
   </td>
   <td>Kann den Denkfehler im Prozess identifizieren und korrigieren
   </td>
  </tr>
  <tr>
   <td><strong>Technische Komplexität</strong>
   </td>
   <td>Gering; ein API-Aufruf, einfache Datenhaltung
   </td>
   <td>Hoch; erfordert Zustandsverwaltung, komplexe Datenbankstruktur, Konversationslogik
   </td>
  </tr>
</table>



## B. Steuerung von Umfang und Tiefe des Feedbacks

Eines der größten Risiken von automatisiertem Feedback ist die kognitive Überlastung des Lernenden. Ein Schüler, der gleichzeitig detaillierte Rückmeldungen zu Rechtschreibung, Satzbau, Argumentationsstruktur und Inhalt erhält, kann diese Fülle an Informationen nicht effektiv verarbeiten. Die Folge ist, dass das Feedback ignoriert wird oder sogar demotivierend wirkt. Eine effektive Feedback-Engine muss daher Mechanismen zur Steuerung von Umfang und Tiefe des Feedbacks implementieren.


### 1. Analyse der kognitiven Überlastung

Die **Cognitive Load Theory (CLT)** bietet den entscheidenden theoretischen Rahmen für das Verständnis dieses Problems.<sup>20</sup> CLT postuliert, dass unser Arbeitsgedächtnis, der Ort der bewussten Informationsverarbeitung, eine sehr begrenzte Kapazität hat.<sup>22</sup> Lernen findet statt, wenn Informationen aus dem Arbeitsgedächtnis erfolgreich in das Langzeitgedächtnis übertragen und dort in bestehende Wissensstrukturen (Schemata) integriert werden.

CLT unterscheidet drei Arten von kognitiver Belastung <sup>23</sup>:



1. **Intrinsische Last:** Die dem Lerninhalt innewohnende Komplexität. Das Erlernen der Grundrechenarten hat eine geringere intrinsische Last als das Verständnis der Quantenmechanik.
2. **Extrinsische Last:** Die Belastung, die durch die Art der Informationsdarbietung entsteht und nicht direkt dem Lernen dient. Unklare Anweisungen, eine überladene Benutzeroberfläche oder eben zu umfangreiches, unstrukturiertes Feedback erzeugen eine hohe extrinsische Last.
3. **Germane Last:** Die "nützliche" Belastung, die durch die mentalen Anstrengungen entsteht, neue Informationen zu verstehen und Schemata im Langzeitgedächtnis aufzubauen.

Das Ziel jeder didaktischen Gestaltung – und somit auch der GUSTAV Feedback Engine – muss es sein, die **extrinsische Last zu minimieren**, um möglichst viel Kapazität des Arbeitsgedächtnisses für die **germane Last** freizuhalten.<sup>25</sup> Ein Feedback, das den Schüler mit zu vielen Korrekturpunkten auf einmal konfrontiert, maximiert die extrinsische Last. Der Schüler ist damit beschäftigt, die verschiedenen Hinweise zu sortieren und zu priorisieren, anstatt sich auf die eigentliche Verarbeitung und das Lernen zu konzentrieren.<sup>2</sup>


### 2. Mechanismen zur Steuerung: Lehrkraft vs. Schüler

Um die kognitive Last zu managen, muss das System den Fokus und die Granularität des Feedbacks steuern können. Die zentrale Frage ist, wer diese Steuerung ausüben sollte: die Lehrkraft, die den Lernprozess gestaltet, oder der Schüler, der den Lernprozess durchläuft.

Lehrkraft-gesteuerte Steuerung (Teacher-Centered):

In diesem Modell legt die Lehrkraft bei der Erstellung der Aufgabe fest, auf welche Aspekte die KI achten soll (z.B. "Nur auf die Argumentationsstruktur achten", "Fokus auf Rechtschreibung und Grammatik").



* **Vorteile:**
    * **Didaktische Ausrichtung:** Das Feedback wird präzise auf die Lernziele der jeweiligen Aufgabe ausgerichtet. Die Lehrkraft kann bewusst Schwerpunkte setzen, die dem aktuellen Lernstand der Klasse entsprechen.<sup>26</sup>
    * **Struktur und Klarheit:** Der Schüler erhält eine klare Orientierung und wird nicht von Aspekten abgelenkt, die für die aktuelle Aufgabe weniger relevant sind. Dies reduziert die extrinsische Last.
* **Nachteile:**
    * **Mangelnde Flexibilität:** Ein Schüler, der zwar an der Argumentationsstruktur arbeiten soll, aber grundlegende Probleme mit dem Satzbau hat, die ihn blockieren, erhält keine Hilfe in diesem Bereich.
    * **Reduzierte Autonomie:** Der Schüler wird in eine passive Rolle gedrängt und hat keine Möglichkeit, selbst zu entscheiden, wo er Unterstützung benötigt. Dies kann die Entwicklung von Selbstregulations- und metakognitiven Fähigkeiten hemmen.

Schüler-gesteuerte Steuerung (Student-Centered):

In diesem Modell kann der Schüler selbst wählen, zu welchen Aspekten er Feedback erhalten möchte (z.B. "Gib mir nur einen Tipp zur Einleitung", "Prüfe die Grammatik in diesem Absatz").



* **Vorteile:**
    * **Förderung der Lernautonomie:** Der Schüler wird zum aktiven Gestalter seines Lernprozesses. Er lernt, seine eigenen Stärken und Schwächen zu reflektieren und gezielt nach Hilfe zu fragen. Dies ist ein Kernaspekt der Selbstregulation.<sup>28</sup>
    * **Bedarfsorientierung:** Das Feedback wird "just-in-time" und genau dort abgerufen, wo der Schüler es benötigt und mental bereit ist, es zu verarbeiten.
* **Nachteile:**
    * **Fehleinschätzung durch Novizen:** Insbesondere lernschwächere Schüler können ihre eigenen Defizite oft nur unzureichend einschätzen. Sie neigen dazu, sich auf oberflächliche Fehler (z.B. Tippfehler) zu konzentrieren, während sie grundlegende strukturelle Probleme übersehen.
    * **Gefahr der Unterforderung:** Ein Schüler könnte aus Bequemlichkeit nur nach einfachem Feedback fragen und die Auseinandersetzung mit komplexeren, anspruchsvolleren Aspekten meiden.

Die Debatte zwischen lehrer- und schülerzentrierten Ansätzen wird oft als Dichotomie dargestellt, doch in der Praxis ist eine Kombination oft am wirkungsvollsten.<sup>26</sup> Ein rein lehrergesteuertes System ignoriert die individuellen Bedürfnisse des Schülers, während ein rein schülergesteuertes System den Schüler ohne die notwendige expertenbasierte Führung lässt.

Die Lösung liegt in einem **hybriden, zweistufigen Kontrollmodell**. Dieses Modell verbindet die didaktische Führung der Lehrkraft mit der prozessualen Autonomie des Schülers.



1. **Stufe 1 (Lehrkraft-Kontrolle): Definition des Möglichkeitsraums.** Die Lehrkraft definiert für jede Aufgabe die *verfügbaren* Feedback-Dimensionen. Sie legt den "Lehrplan" für das Feedback fest und stellt sicher, dass dieser auf die Lernziele abgestimmt ist. Sie definiert sozusagen die Leitplanken, innerhalb derer sich der Schüler bewegen kann.
2. **Stufe 2 (Schüler-Kontrolle): Navigation im Möglichkeitsraum.** Der Schüler wählt aus den von der Lehrkraft freigegebenen Dimensionen aus, zu welchem Aspekt er *jetzt* Feedback erhalten möchte und in welcher Tiefe (z.B. ein kurzer Hinweis vs. eine detaillierte Erklärung). Dies ermöglicht es dem Schüler, die kognitive Last selbst zu steuern und das Feedback in verdaubaren Portionen ("chunks") abzurufen, was dem Arbeitsgedächtnis entgegenkommt.<sup>31</sup>

Dieses Modell schafft eine "Zone der proximalen Entwicklung" (Wygotski), in der die Lehrkraft den Rahmen für die Herausforderung vorgibt, während die KI als anpassungsfähiges Werkzeug (Scaffold) dient, das der Schüler nach Bedarf einsetzen kann.


### 3. UI/UX für die Steuerung

Die Benutzeroberfläche muss dieses zweistufige Modell einfach und intuitiv abbilden.

Lehrer-Interface (bei der Aufgabenerstellung):

Die Lehrkraft benötigt eine einfache Möglichkeit, die Feedback-Fokusbereiche auszuwählen. Ein komplexer Regel-Editor 33 wäre hier kontraproduktiv. Eine Checkliste mit vordefinierten und benutzerdefinierten Optionen ist vorzuziehen.34



---
**GUSTAV AI Feedback-Fokus**

Wählen Sie die Aspekte aus, zu denen die KI Feedback geben darf.



* [✓] Rechtschreibung & Grammatik
* [✓] Argumentationsstruktur & roter Faden
* [✓] Klarheit der These
* [ ] Verwendung von Quellen & Zitaten
* [ ] Stil & Ausdruck
* [+] Eigenes Kriterium hinzufügen...



---
Schüler-Interface (während der Bearbeitung):

Die Darstellung hängt vom gewählten Feedback-Modus ab.



* **Im einmaligen Modus:** Der generierte Bericht wird durch die von der Lehrkraft gewählten Fokusbereiche strukturiert.
* **Im interaktiven Modus:** Der Schüler erhält aktive Steuerungselemente. Anstatt nur einen Text einzugeben, kann er die KI gezielt anweisen:



---
*Schüler gibt einen Absatz ein oder markiert einen Textabschnitt.*

**GUSTAV:** Was möchtest du zu diesem Abschnitt wissen?

Argumentationsstruktur prüfen Stil verbessern Grammatik checken

*Nach Auswahl, z.B. "Argumentationsstruktur prüfen":*

**GUSTAV:** Okay, ich schaue mir die Argumentation an. Wie detailliert soll mein Feedback sein?


## Gib mir nur einen Tipp Zeige mir das Hauptproblem Gib mir eine ausführliche Analyse

Dieses Design gibt dem Schüler die Kontrolle über das "Was" (innerhalb des von der Lehrkraft gesetzten Rahmens) und das "Wie viel" des Feedbacks und ist somit ein direktes Instrument zur Selbstregulation der kognitiven Last.


## C. Technische Umsetzung & KI-Architektur

Die erfolgreiche Implementierung der GUSTAV Feedback Engine mit kleinen, lokalen 8B-LLMs hängt entscheidend von einer durchdachten KI-Architektur ab. Effiziente Kontextbereitstellung, eine robuste, mehrstufige Prompting-Strategie und der gezielte Einsatz des DSPy-Frameworks sind die drei Säulen dieser Architektur.


### 1. Kontextbereitstellung: Das A und O für kleine Modelle

Kleine LLMs sind im Vergleich zu ihren großen Pendants deutlich empfindlicher gegenüber irrelevantem oder schlecht strukturiertem Kontext.<sup>5</sup> Die Qualität des generierten Feedbacks ist eine direkte Funktion der Qualität und Präzision des Inputs.<sup>36</sup>



* **Minimaler vs. Optimaler Kontext:**
    * **Minimal notwendig:** Um überhaupt eine rudimentäre Rückmeldung geben zu können, benötigt die KI die Aufgabenstellung und die Schülerlösung.
    * **Optimal:** Für qualitativ hochwertiges, didaktisch wertvolles Feedback sind weitere Informationen unerlässlich: das explizite Lernziel der Aufgabe, detaillierte Bewertungskriterien (eine Rubrik), eine Musterlösung als Referenz und, falls zutreffend, relevante Auszüge aus den Lernmaterialien, auf die sich die Aufgabe bezieht.
* Strategie zur Definition des Feedback-Fokus: \
Die Art und Weise, wie die Lehrkraft die Bewertungskriterien und die Musterlösung bereitstellt, hat einen direkten Einfluss auf die Präzision des LLM-Prompts. Eine einzelne, flexible Textbox für den "Feedback-Fokus" ist zwar für die Lehrkraft einfach zu bedienen, birgt aber erhebliche Nachteile für die KI. Sie verleitet zu narrativen, unstrukturierten Eingaben, die für ein kleines LLM schwer zu parsen sind und das Signal-Rausch-Verhältnis im Prompt verschlechtern. \
Eine weitaus robustere Methode ist die Verwendung **separater, strukturierter Datenbankfelder** für verschiedene Kontexttypen (z.B. evaluation_criteria, model_solution, learning_objective). Dieser Ansatz zwingt die Lehrkraft zu einer klareren, kategorisierten Eingabe. Diese strukturierten Daten können dann im Backend programmgesteuert zu einem hochoptimierten Prompt mit klaren Trennern und Überschriften (z.B. ### Bewertungskriterien ###, ### Musterlösung ###) zusammengesetzt werden. Dies maximiert die Klarheit und stellt sicher, dass das 8B-Modell seine begrenzten kognitiven Ressourcen auf die relevanten Informationen konzentrieren kann. Der geringfügig höhere Aufwand bei der UI-Gestaltung wird durch eine signifikant höhere Zuverlässigkeit und Qualität des generierten Feedbacks mehr als aufgewogen.

**Tabelle C.1: Vergleich der Strategien zur Kontextbereitstellung**


<table>
  <tr>
   <td>Strategie
   </td>
   <td>Beschreibung
   </td>
   <td>Vorteile (Lehrkraft)
   </td>
   <td>Vorteile (KI-Präzision)
   </td>
   <td>Nachteile
   </td>
   <td>Empfehlung für GUSTAV
   </td>
  </tr>
  <tr>
   <td><strong>Einzelnes, flexibles feedback_focus-Feld</strong>
   </td>
   <td>Ein einziges Textfeld, in das die Lehrkraft alle Anweisungen, Kriterien und Beispiele frei eingibt.
   </td>
   <td>Maximale Einfachheit, keine vorgegebene Struktur.
   </td>
   <td>Gering. Hohes Risiko für unklare, mehrdeutige oder "verrauschte" Prompts.
   </td>
   <td>Erfordert, dass das LLM die Intention der Lehrkraft aus unstrukturiertem Text interpretieren muss, was für kleine Modelle fehleranfällig ist.
   </td>
   <td><strong>Nicht empfohlen.</strong>
   </td>
  </tr>
  <tr>
   <td><strong>Separate, strukturierte Datenbankfelder</strong>
   </td>
   <td>Dedizierte Felder für Bewertungskriterien, Musterlösung, Lernziel etc.
   </td>
   <td>Führt die Lehrkraft zu präziseren Eingaben. Geringfügig höherer UI-Aufwand.
   </td>
   <td>Sehr hoch. Ermöglicht die Erstellung von sauberen, klar strukturierten Prompts mit hohem Signal-Rausch-Verhältnis.
   </td>
   <td>Erfordert ein durchdachteres UI-Design für die Aufgabenerstellung.
   </td>
   <td><strong>Dringend empfohlen.</strong>
   </td>
  </tr>
</table>




* Umgang mit externem Material: Eine pragmatische RAG-light-Strategie: \
Häufig beziehen sich Aufgaben auf externe Texte (z.B. eine Kurzgeschichte, einen Sachtext), die das Kontextfenster eines 8B-Modells bei weitem sprengen würden. Hier ist eine "Retrieval-Augmented Generation" (RAG)-Strategie erforderlich. Für GUSTAV wird eine leichtgewichtige, lokal ausführbare "RAG-light"-Pipeline vorgeschlagen, deren Ziel nicht die Beantwortung von Fragen aus dem Dokument, sondern die gezielte Injektion von relevantem Kontext in den Feedback-Prompt ist. Leichte, CPU-freundliche RAG-Implementierungen sind mit Werkzeugen wie ChromaDB und effizienten Embedding-Modellen realisierbar.38 \
**Technische Pipeline (RAG-light):**
    1. **Indizierung (einmalig pro Aufgabe):** Wenn eine Lehrkraft ein Dokument (z.B. PDF, TXT) hochlädt, wird dieses serverseitig verarbeitet.
        * Mit einer Bibliothek wie UnstructuredLoader wird der Text extrahiert.<sup>38</sup>
        * Der Text wird mit einem RecursiveCharacterTextSplitter in handhabbare, sich überlappende Abschnitte (Chunks) von z.B. 512 Tokens zerlegt.<sup>41</sup>
        * Für jeden Chunk wird mit einem kleinen, lokalen Embedding-Modell (z.B. nomic-embed-text, bereitgestellt über Ollama) ein Vektor-Embedding erzeugt.
        * Die Chunks und ihre Embeddings werden in einer lokalen ChromaDB-Vektordatenbank gespeichert, die mit der assignment_id verknüpft ist.
    2. **Retrieval (bei jeder Feedback-Anfrage):**
        * Wenn ein Schüler Feedback anfordert, wird eine Suchanfrage (Query) generiert. Diese kann aus der Aufgabenstellung und dem spezifischen Satz oder Absatz der Schülerlösung bestehen, zu dem Feedback gewünscht wird.
        * Mit dieser Query werden die Top-k (z.B. k=3) semantisch ähnlichsten Chunks aus der ChromaDB-Sammlung abgerufen.
    3. **Injektion:**
        * Der Text dieser abgerufenen Chunks wird in den finalen LLM-Prompt unter einer klaren Überschrift wie ### Relevante Auszüge aus dem Lernmaterial ### eingefügt.

Dieser Ansatz stellt sicher, dass das LLM sein Feedback auf die relevanten Passagen des Quellenmaterials stützen kann, ohne dass das Kontextfenster überlastet wird.


### 2. Prompting-Strategie & Mehrstufigkeit

Eine einzelne, komplexe Anweisung an ein kleines LLM führt oft zu unzuverlässigen Ergebnissen. Die Zerlegung komplexer Aufgaben in eine Kette einfacherer, spezialisierter Schritte ist eine grundlegende Technik des Prompt Engineering und für die Arbeit mit 8B-Modellen unerlässlich.<sup>7</sup>



* Bestätigung des mehrstufigen Prozesses (Analyse → Feedback): \
Der vorgeschlagene Zwei-Schritt-Prozess ist die robusteste Vorgehensweise. Ein einziger Prompt, der ein 8B-Modell anweist, eine Schülerlösung zu analysieren, Fehler zu identifizieren, diese gegen eine Rubrik zu bewerten UND dann ein didaktisch wertvolles, unterstützendes Feedback zu formulieren, ist kognitiv zu anspruchsvoll für das Modell. Die Trennung in zwei spezialisierte Aufgaben reduziert die Komplexität jedes einzelnen Schrittes drastisch:
    1. **Analyse-Schritt:** Ein rein logischer, analytischer Task. Das Modell konzentriert sich darauf, die Schülerlösung mit den Kriterien abzugleichen und seine Ergebnisse in einem strukturierten Format (JSON) auszugeben.
    2. **Feedback-Generierungs-Schritt:** Ein kreativer, sprachlicher Task. Das Modell erhält die strukturierte Analyse als Input und konzentriert sich ausschließlich darauf, diese in eine pädagogisch wertvolle, sprachlich angemessene Form zu bringen, die der definierten Persona entspricht.

    Diese Modularität erhöht nicht nur die Zuverlässigkeit, sondern erleichtert auch das Debugging und die spätere Optimierung mit DSPy.

* Entwicklung robuster Basis-Prompts: \
Die folgenden Prompts dienen als Vorlagen. Sie werden dynamisch mit den kontextuellen Informationen aus der Datenbank befüllt. \
**Schritt 1: Analyse-Prompt (Basis)** \
Du bist ein präziser und objektiver Analyse-Assistent. Deine Aufgabe ist es, die Schülerlösung ausschließlich anhand der vorgegebenen Kriterien und der Musterlösung zu bewerten. Deine Analyse muss streng faktenbasiert sein und sich auf die bereitgestellten Informationen stützen. Gib deine Analyse in einem strukturierten JSON-Format aus. \
 \
### Aufgabenstellung \
{{assignment_description}} \
 \
### Bewertungskriterien \
{{evaluation_criteria}} \
 \
### Musterlösung (falls vorhanden) \
{{model_solution}} \
 \
### Relevante Auszüge aus dem Lernmaterial \
{{retrieved_context_chunks}} \
 \
### Schülerlösung \
{{student_answer}} \
 \
--- \
ANWEISUNG: \
Analysiere die Schülerlösung Schritt für Schritt. Identifiziere für jedes Bewertungskriterium spezifische Stärken und Schwächen. Zitiere für jeden Punkt wörtlich den relevanten Teil der Schülerlösung als Beleg. \
 \
Gib deine Ausgabe AUSSCHLIESSLICH als valides JSON-Objekt aus. Das Objekt soll zwei Schlüssel haben: "strengths" und "weaknesses". Jeder Schlüssel enthält eine Liste von Objekten, wobei jedes Objekt die Felder "criterion" (das exakte Kriterium), "quote_from_solution" (das wörtliche Zitat) und "analysis" (deine kurze, objektive Analyse) enthält. Formuliere keine subjektiven Meinungen. \
 \
**Schritt 2: Feedback-Prompt (Basis)** \
Du bist GUSTAV, ein unterstützender, geduldiger und motivierender Lern-Coach für Schülerinnen und Schüler der Sekundarstufe. Deine Tonalität ist immer positiv, ermutigend und auf Augenhöhe. Du sprichst den Schüler direkt mit "Du" an. Dein Feedback ist IMMER formativ, spezifisch, handlungsorientiert und nicht-wertend. \
 \
Dein Ziel ist es, dem Schüler zu helfen, die drei Kernfragen nach Hattie zu beantworten: \
1. Wo stehe ich? (Feed Up & Feedback) \
2. Wie geht es voran? (Feedback) \
3. Wo geht es als Nächstes hin? (Feed Forward) \
 \
Basierend auf der folgenden strukturierten Analyse der Schülerarbeit, formuliere nun ein lernförderliches, dialogisches Feedback. \
 \
### Analyse der Stärken und Schwächen \
{{analysis_json}} \
 \
--- \
ANWEISUNG: \
Formuliere das Feedback nach folgendem Schema: \
1.  **Positiver Einstieg:** Beginne mit einer spezifischen, positiven Beobachtung. Wähle eine konkrete Stärke aus der Analyse und erkläre, warum sie gut ist. (z.B. "Mir ist positiv aufgefallen, wie du...") \
2.  **Wichtigster Verbesserungspunkt:** Konzentriere dich auf EINEN zentralen Verbesserungspunkt aus der Analyse. Erkläre das Problem klar und verständlich. Vermeide wertende Sprache (nicht "das ist falsch", sondern "hier gibt es noch Potenzial für mehr Klarheit"). \
3.  **Konkreter nächster Schritt (Feed Forward):** Gib einen klaren, umsetzbaren Tipp oder stelle eine gezielte Frage, die dem Schüler hilft, den nächsten Schritt zu gehen. (z.B. "Versuche doch mal, diesen Satz umzuformulieren, indem du...", "Welches Beispiel aus dem Text könnte dieses Argument noch stärker machen?"). \
4.  **Ermutigender Abschluss:** Schließe mit einer motivierenden Bemerkung, die den Schüler zum Weitermachen anregt. (z.B. "Du bist auf einem sehr guten Weg. Ich bin gespannt auf deine Überarbeitung!"). \

* **Dynamische Anpassung:** Die Logik zur Anpassung an verschiedene Aufgabentypen (z.B. "Fasse zusammen" vs. "Beurteile") wird nicht im Prompt hartcodiert. Sie wird durch die evaluation_criteria gesteuert, die von der Lehrkraft bereitgestellt werden. Der Analyse-Prompt ist universell; er wendet die jeweils gültigen Kriterien an. Dies macht das System flexibel und erweiterbar, ohne dass für jeden neuen Aufgabentyp ein neuer Prompt entwickelt werden muss.


### 3. Rolle von DSPy: Vom Programmieren zum Optimieren

DSPy ist das ideale Framework, um diese mehrstufige, kontextabhängige Pipeline zu orchestrieren. Es erlaubt uns, die Logik deklarativ zu beschreiben und die mühsame, manuelle Prompt-Optimierung durch einen algorithmischen Prozess zu ersetzen.<sup>44</sup>



* Startpunkt mit dspy.Predict und dspy.Module: \
Die Implementierung beginnt mit der Definition der beiden Schritte als separate dspy.Predict-Module, da dies der einfachste und modularste Ansatz ist.46 \
Python \
import dspy \
 \
class AnalyzeAnswer(dspy.Signature): \
    """Analyzes a student's answer based on criteria and context, providing a structured JSON output.""" \
    assignment_description = dspy.InputField() \
    evaluation_criteria = dspy.InputField() \
    student_answer = dspy.InputField() \
    retrieved_context_chunks = dspy.InputField(desc="Relevant snippets from learning material.") \
    analysis_json = dspy.OutputField(desc="A structured JSON with 'strengths' and 'weaknesses'.") \
 \
class GenerateFeedback(dspy.Signature): \
    """Generates formative feedback based on a structured analysis.""" \
    analysis_json = dspy.InputField() \
    formative_feedback = dspy.OutputField(desc="Supportive, actionable feedback for the student.") \
 \
class GustavFeedbackPipeline(dspy.Module): \
    def __init__(self): \
        super().__init__() \
        self.analyzer = dspy.Predict(AnalyzeAnswer) \
        self.feedback_generator = dspy.Predict(GenerateFeedback) \
 \
    def forward(self, assignment_description, evaluation_criteria, student_answer, retrieved_context_chunks): \
        analysis_result = self.analyzer( \
            assignment_description=assignment_description, \
            evaluation_criteria=evaluation_criteria, \
            student_answer=student_answer, \
            retrieved_context_chunks=retrieved_context_chunks \
        ) \
        feedback_result = self.feedback_generator(analysis_json=analysis_result.analysis_json) \
        return feedback_result \

* Evolution zu dspy.ChainOfThought: \
Insbesondere der Analyse-Schritt profitiert von einer expliziten Anweisung zum schrittweisen Denken. Für komplexe Analysen, bei denen mehrere Kriterien gleichzeitig geprüft werden müssen, kann das dspy.Predict-Modul durch ein dspy.ChainOfThought-Modul ersetzt werden.45 Dies instruiert das LLM, seinen Denkprozess zu explizieren, bevor es das finale JSON generiert, was die Genauigkeit und Zuverlässigkeit bei kleinen Modellen oft signifikant erhöht. Die Signatur würde entsprechend angepasst: \
... -> reasoning, analysis_json.
* Vorbereitung für die Optimierung mit Telepromptern: \
Der entscheidende Vorteil von DSPy manifestiert sich in der Optimierungsphase.44 Um diese zu ermöglichen, muss von Beginn an ein qualitativ hochwertiger Datensatz aufgebaut werden.
    * **Datensatz-Erstellung:** Es muss ein Prozess etabliert werden, um Beispiele für exzellentes Feedback zu sammeln. Dies können von Lehrkräften manuell erstellte oder validierte Feedback-Instanzen sein. Jedes Beispiel wird als dspy.Example-Objekt gespeichert und enthält alle Eingabefelder (Aufgabe, Kriterien, Schülerlösung) sowie die "goldenen" Ausgabefelder (analysis_json, formative_feedback).
    * **Optimierungsprozess:** Sobald ein kleiner Datensatz von 20-50 qualitativ hochwertigen Beispielen vorliegt, kann ein DSPy-Compiler (Teleprompter) wie BootstrapFewShot eingesetzt werden. Dieser Compiler testet verschiedene Kombinationen der Trainingsbeispiele als Few-Shot-Demonstrationen, um die effektivsten Prompts für die AnalyzeAnswer- und GenerateFeedback-Module zu finden. Er "kompiliert" das DSPy-Programm zu einer optimierten Version, die diese gelernten Demonstrationen automatisch in die Prompts einfügt. Dieser algorithmische Ansatz ersetzt wochenlanges manuelles "Prompt-Tuning" und ist der Kern der DSPy-Philosophie.


## D. Entlastung der Lehrkräfte

Ein KI-gestütztes Feedback-System entfaltet sein volles Potenzial erst, wenn es nicht nur die Korrekturarbeit erleichtert, sondern Lehrkräfte auch bei der Vorbereitung und Erstellung von Aufgaben aktiv unterstützt. GUSTAV kann hier durch einen intelligenten, hybriden Ansatz einen erheblichen Mehrwert schaffen.


### 1. Optionale Nutzung stärkerer LLMs zur Kriterienerstellung

Das Formulieren von klaren, präzisen und didaktisch sinnvollen Bewertungskriterien (dem feedback_focus) ist eine anspruchsvolle und zeitintensive Aufgabe. Während ein lokales 8B-Modell gut darin ist, nach vorgegebenen Regeln Feedback zu geben, sind größere, leistungsfähigere Modelle (wie GPT-4o oder Claude 3 Opus) deutlich überlegen, wenn es um die kreative und nuancierte Aufgabe geht, solche Kriterien überhaupt erst zu erstellen.<sup>49</sup>

Gleichzeitig ist der Einsatz von Cloud-basierten APIs für die Verarbeitung von Schülerdaten im europäischen Schulkontext aus Datenschutzgründen (DSGVO/GDPR) höchst problematisch und in der Regel nicht zulässig.<sup>52</sup>

Diese beiden Aspekte lassen sich durch eine **hybride KI-Architektur** in Einklang bringen, die strikt zwischen Lehrer- und Schüler-Workflows trennt:



* **Schüler-Workflow (Lokal):** Jegliche Verarbeitung von Schülerlösungen und die Generierung von Feedback an Schüler erfolgt **ausschließlich** über das lokal gehostete 8B-LLM. Es werden zu keinem Zeitpunkt Schülerdaten an externe Server gesendet.
* **Lehrer-Workflow (Optional Cloud):** Bei der Erstellung einer neuen Aufgabe wird der Lehrkraft eine **optionale Assistenzfunktion** angeboten, z.B. ein Button mit der Beschriftung "Hilf mir bei der Erstellung der Bewertungskriterien".
    * Wenn die Lehrkraft diese Funktion aktiviert, sendet das System ausschließlich die anonymen Aufgabendetails (z.B. Titel, Beschreibung, Fach, Klassenstufe) an eine externe, leistungsstarke LLM-API.
    * Die API generiert einen Vorschlag für eine Bewertungsrubrik oder eine Musterlösung.
    * Dieser Vorschlag wird der Lehrkraft im Frontend angezeigt, die ihn dann bearbeiten, anpassen und **lokal** in der GUSTAV-Datenbank speichern kann.

**Technische und datenschutzrechtliche Implikationen:**



* **Technisch:** Diese Funktion erfordert eine serverseitige Integration mit einer externen API (z.B. OpenAI, Anthropic), ein sicheres Management von API-Schlüsseln und idealerweise Mechanismen zur Kostenkontrolle.
* **Datenschutz (DSGVO):** Die Umsetzung muss strengen Kriterien folgen:
    * **Opt-In:** Die Funktion darf nur auf expliziten Wunsch der Lehrkraft aktiviert werden.
    * **Transparenz:** Es muss eine klare und verständliche Information angezeigt werden, die darüber aufklärt, dass die (anonymen) Aufgabendaten zur Bearbeitung an einen externen Dienstleister (z.B. "OpenAI in den USA") gesendet werden.
    * **Keine Schülerdaten:** Es muss technisch sichergestellt sein, dass niemals personenbezogene Daten von Schülern in diesen API-Aufrufen enthalten sind.
    * **Datenverarbeitungsvertrag:** Der Betreiber der GUSTAV-Plattform (die Schule oder der Träger) sollte einen Auftragsverarbeitungsvertrag (AVV) bzw. ein Data Processing Addendum (DPA) mit dem API-Anbieter abschließen, um die datenschutzrechtlichen Pflichten zu regeln.<sup>54</sup>

Dieser hybride Ansatz bietet das Beste aus beiden Welten: die volle Entlastung für Lehrkräfte durch State-of-the-Art-KI bei der Vorbereitung und die maximale Datensicherheit für Schüler bei der Bearbeitung.


### 2. Weitere KI-gestützte Unterstützungsmöglichkeiten

Aufbauend auf derselben hybriden Architektur können Lehrkräften weitere zeitsparende Werkzeuge angeboten werden, die die Akzeptanz und den Nutzen der Plattform weiter steigern <sup>55</sup>:



* **Generierung von Aufgabenvariationen:** Aus einer bestehenden Aufgabe kann die KI auf Knopfdruck alternative Fragestellungen oder Szenarien entwickeln, um z.B. für verschiedene Lerngruppen zu differenzieren.
* **Anpassung des Schwierigkeitsgrades:** Die KI kann eine Aufgabe für leistungsstärkere Schüler anspruchsvoller formulieren oder für Schüler mit Förderbedarf vereinfachen ("Binnendifferenzierung").
* **Erstellung von Musterlösungen:** Basierend auf der Aufgabenstellung und den erstellten Kriterien kann die KI eine detaillierte Musterlösung generieren, die der Lehrkraft als Referenz für die Bewertung dient.
* **Generierung von Lernzielen:** Die KI kann basierend auf der Aufgabe passende, kompetenzorientierte Lernziele vorschlagen.

Diese Funktionen positionieren GUSTAV nicht nur als Feedback-Werkzeug, sondern als umfassenden digitalen Assistenten, der Lehrkräfte im gesamten Unterrichtszyklus unterstützt.


## E. Risiken und deren Mitigation

Die Implementierung eines KI-gestützten Feedback-Systems birgt inhärente Risiken, die proaktiv adressiert werden müssen. Eine verantwortungsvolle Entwicklung erfordert eine umfassende Analyse potenzieller Fehlerquellen und die Implementierung einer mehrschichtigen Strategie aus technischen und prozessualen Gegenmaßnahmen.


### 1. Identifikation der größten Risiken



* **Sachlich falsches Feedback (Halluzinationen):** Das LLM generiert Fakten, Zitate oder Korrekturen, die plausibel klingen, aber sachlich falsch sind. Dies ist eines der bekanntesten Probleme von LLMs und kann den Lernprozess direkt untergraben.<sup>57</sup>
* **Inkonsistente Bewertungen:** Das System bewertet identische oder sehr ähnliche Fehler bei verschiedenen Schülern oder zu unterschiedlichen Zeitpunkten inkonsistent. Dies untergräbt die Fairness und die Verlässlichkeit des Feedbacks.<sup>49</sup>
* **Zu generisches oder oberflächliches Feedback:** Die KI gibt vage, nichtssagende Rückmeldungen (z.B. "Guter Ansatz!", "Das könntest du noch verbessern."), die dem Schüler keine konkreten, handlungsorientierten Hinweise geben und somit den Kriterien von Hattie und Shute nicht entsprechen.<sup>60</sup>
* **Umgehung des Lernprozesses ("Gaming the System"):** Schüler nutzen den interaktiven Modus nicht zum Lernen, sondern um durch schnelles Ausprobieren ("Trial and Error") iterativ die von der KI akzeptierte Lösung zu finden, ohne die zugrundeliegenden Konzepte zu verstehen.<sup>61</sup>
* **Bias und Fairness:** Das LLM reproduziert unbewusste Vorurteile (Bias) aus seinen Trainingsdaten. Es könnte beispielsweise bestimmte sprachliche Stile bevorzugen, die mit bestimmten sozioökonomischen oder kulturellen Hintergründen korrelieren, und so Schüler unbeabsichtigt benachteiligen.<sup>57</sup>


### 2. Konkrete technische und prozessuale Gegenmaßnahmen

Eine effektive Risikominimierung erfordert eine Kombination aus präventiven Maßnahmen in der Architektur, detektiven Maßnahmen während des Betriebs und transparenten, pädagogischen Rahmenbedingungen.

Mehrschichtige Verteidigung gegen Halluzinationen und sachliche Fehler:

Da Halluzinationen nicht vollständig eliminiert werden können, muss eine "Defense in Depth"-Strategie verfolgt werden.59



1. **Prävention durch Grounding:** Die in Abschnitt C.1 beschriebene RAG-light-Architektur ist die erste und wichtigste Verteidigungslinie. Indem der Prompt mit relevanten Auszügen aus den Lernmaterialien "geerdet" (grounded) wird, wird die Wahrscheinlichkeit, dass das LLM Fakten erfindet, signifikant reduziert.
2. **Detektion durch Selbst-Verifikation:** Die Prompt-Kette kann um einen Verifikationsschritt erweitert werden. Nachdem das Feedback generiert wurde, wird das LLM in einem zweiten Aufruf instruiert: "Überprüfe jede Tatsachenbehauptung im folgenden Feedbacktext. Wenn eine Aussage nicht direkt durch die bereitgestellten Lernmaterialien oder die Musterlösung gestützt wird, markiere sie als 'unsicher' oder formuliere sie als Frage um."
3. **Transparenz in der UI:** Jedes von der KI generierte Feedback muss unmissverständlich als solches gekennzeichnet sein. Ein permanenter, gut sichtbarer Disclaimer ist obligatorisch: "Dieses Feedback wurde von GUSTAV, einer KI, erstellt. Es dient als Anregung für deine Überarbeitung. Überprüfe wichtige Fakten und sprich im Zweifel immer mit deiner Lehrkraft."
4. **Konfidenz-Scoring (fortgeschritten):** Viele LLM-APIs (auch über Ollama) können die Log-Wahrscheinlichkeiten (logprobs) für die generierten Tokens ausgeben. Wenn das Modell eine Faktenaussage mit sehr niedriger kumulativer Wahrscheinlichkeit generiert, deutet dies auf eine hohe Unsicherheit hin. Die UI kann solche Passagen visuell hervorheben (z.B. durch eine gepunktete Unterstreichung), um den Schüler zur Vorsicht zu mahnen.<sup>58</sup>

Pädagogische und technische Maßnahmen gegen die Umgehung des Lernprozesses:

Das "Gaming" des Systems ist weniger ein technisches als ein pädagogisches Problem, das aber durch technisches Design beeinflusst werden kann.65



1. **Rate Limiting:** Die Anzahl der Feedback-Anfragen pro Schüler und Zeiteinheit (z.B. maximal 3 Anfragen in 15 Minuten) kann technisch begrenzt werden. Dies verlangsamt den "Trial and Error"-Prozess und zwingt den Schüler, über das erhaltene Feedback nachzudenken, bevor er die nächste Anfrage stellt.
2. **Transparenz für die Lehrkraft:** Die in Abschnitt A.2 entworfene, versionszentrierte Datenbank speichert die gesamte Interaktionshistorie. Lehrkräfte müssen die Möglichkeit haben, diesen Verlauf einzusehen, um zu erkennen, ob ein Schüler konstruktiv mit dem System arbeitet oder es nur ausnutzt.
3. **Förderung der Metakognition:** Das System kann aktiv zur Reflexion anregen. Nach der Einreichung einer überarbeiteten Version könnte die KI eine metakognitive Frage stellen: "Beschreibe kurz, welche Änderungen du auf Basis meines letzten Feedbacks vorgenommen hast und warum du denkst, dass dies eine Verbesserung ist." Die Antwort des Schülers wird ebenfalls gespeichert und ist für die Lehrkraft einsehbar. Dies verschiebt den Fokus von der reinen Lösungsfindung hin zur bewussten Auseinandersetzung mit dem Lernprozess.

Die folgende Matrix fasst die Risiken und die vorgeschlagenen, mehrschichtigen Gegenmaßnahmen systematisch zusammen.

**Tabelle E.1: Risiko-Mitigations-Matrix für die GUSTAV Feedback Engine**


<table>
  <tr>
   <td>Risiko
   </td>
   <td>Wahrscheinlichkeit
   </td>
   <td>Auswirkung
   </td>
   <td>Technische Mitigation
   </td>
   <td>Pädagogische/Prozess-Mitigation
   </td>
  </tr>
  <tr>
   <td><strong>Sachliche Fehler (Halluzination)</strong>
   </td>
   <td>Mittel
   </td>
   <td>Hoch
   </td>
   <td>1. Grounding durch RAG-light. 2. Selbst-Verifikations-Schritt im Prompt. 3. Konfidenz-Scoring (logprobs) zur Kennzeichnung unsicherer Aussagen.
   </td>
   <td>1. Permanenter, klarer Disclaimer in der UI. 2. Schulung der Schüler im kritischen Umgang mit KI-generierten Inhalten (AI Literacy). 3. Möglichkeit für Schüler, fehlerhaftes Feedback zu melden.
   </td>
  </tr>
  <tr>
   <td><strong>Inkonsistente Bewertung</strong>
   </td>
   <td>Mittel
   </td>
   <td>Hoch
   </td>
   <td>1. Verwendung strukturierter Kriterien (JSON-Input). 2. Einsatz von dspy.ChainOfThought für einen nachvollziehbaren Analyseprozess. 3. Hohe Temperatur-Einstellungen (temperature=0.1) für deterministischere Ausgaben.
   </td>
   <td>1. Lehrkräfte sollten Stichproben durchführen. 2. Möglichkeit für Schüler, eine manuelle Überprüfung durch die Lehrkraft anzufordern, wenn sie eine Bewertung für unfair halten.
   </td>
  </tr>
  <tr>
   <td><strong>Generisches Feedback</strong>
   </td>
   <td>Hoch (bei kleinen Modellen)
   </td>
   <td>Mittel
   </td>
   <td>1. Mehrstufiger Prompt (Analyse → Feedback). 2. Sehr spezifische Anweisungen im Feedback-Prompt (Hattie-Fragen, positiver Einstieg, konkreter nächster Schritt). 3. DSPy-Optimierung mit "Gold-Standard"-Beispielen für spezifisches Feedback.
   </td>
   <td>1. Lehrkräfte sollten bei der Erstellung der Bewertungskriterien auf Spezifität achten. 2. Gesammelte Beispiele für gutes/schlechtes Feedback zur kontinuierlichen Verbesserung des Systems nutzen.
   </td>
  </tr>
  <tr>
   <td><strong>Umgehung des Lernprozesses</strong>
   </td>
   <td>Hoch
   </td>
   <td>Hoch
   </td>
   <td>1. Rate Limiting für Feedback-Anfragen. 2. Lückenlose Protokollierung der gesamten Interaktions- und Versionshistorie. 3. Implementierung von metakognitiven Reflexionsfragen.
   </td>
   <td>1. Lehrkräften Zugriff auf die Lernhistorie geben und sie schulen, diese zu interpretieren. 2. Aufgaben so gestalten, dass sie höhere Denkprozesse erfordern, die nicht leicht "erraten" werden können (z.B. durch persönliche Reflexionen).<sup>65</sup>
   </td>
  </tr>
  <tr>
   <td><strong>Bias & Fairness</strong>
   </td>
   <td>Mittel
   </td>
   <td>Hoch
   </td>
   <td>1. Verwendung von Prompts, die explizit zu neutraler, nicht-wertender Sprache anweisen. 2. Implementierung eines "Bias-Check"-Schrittes, bei dem die KI ihr eigenes Feedback auf potenziell voreingenommene Formulierungen überprüft.
   </td>
   <td>1. Regelmäßige Audits der Systemausgaben durch diverse Lehrkräfte. 2. Etablierung eines klaren Kanals, über den Schüler und Lehrkräfte als voreingenommen empfundenes Feedback melden können. 3. Transparente Kommunikation über die Grenzen und potenziellen Biases von KI.
   </td>
  </tr>
</table>



## Schlussfolgerung: Ein pragmatischer Weg zu wirksamem KI-Feedback

Dieses Konzept skizziert eine Architektur für die GUSTAV Feedback Engine, die das pädagogisch Wünschenswerte mit dem technisch Machbaren in Einklang bringt. Der Kern des Ansatzes liegt in der Erkenntnis, dass kleine, lokale LLMs keine Alleskönner sind, aber bei sorgfältiger Orchestrierung zu hochwirksamen Werkzeugen für formatives Feedback werden können.

**Zusammenfassung der strategischen Empfehlungen:**



1. **Hybrides Feedback-Modell:** Implementierung eines von der Lehrkraft konfigurierbaren Modus für **einmaliges (statisches) oder interaktives Feedback**, um unterschiedlichen Aufgabentypen und Lernzielen gerecht zu werden.
2. **Zweistufige Feedback-Kontrolle:** Etablierung eines Kontrollsystems, bei dem die **Lehrkraft den Rahmen** der Feedback-Aspekte vorgibt und der **Schüler den Detailgrad und Zeitpunkt** des Feedbacks wählt, um kognitive Überlastung zu vermeiden und die Lernautonomie zu fördern.
3. **Modulare Zwei-Schritt-KI-Architektur:** Aufbau einer robusten Pipeline in DSPy, die den Prozess in **Analyse und Feedback-Generierung** trennt. Diese Architektur muss auf hochstrukturierten Kontextdaten und einem pragmatischen **RAG-light-Ansatz** basieren, um die Leistung kleiner LLMs zu maximieren.
4. **Hybrides KI-Modell zur Lehrerentlastung:** Nutzung eines **optionalen, API-basierten Zugriffs auf leistungsstärkere LLMs ausschließlich für Lehrkräfte** zur Unterstützung bei der Aufgabenerstellung (z.B. Rubriken), bei gleichzeitigem Schutz aller Schülerdaten durch rein lokale Verarbeitung.
5. **Mehrschichtige Risikomitigation:** Implementierung einer umfassenden Strategie zur Risikominimierung, die **präventive technische Maßnahmen** (Grounding, strukturierte Prompts), **detektive Mechanismen** (Selbst-Verifikation, Konfidenz-Scores) und **pädagogisch-prozessuale Rahmenbedingungen** (Transparenz, Metakognition, AI Literacy) kombiniert.

**Vorschlag für eine Implementierungs-Roadmap:**

Ein phasenweiser Ansatz ermöglicht es dem Entwicklungsteam, frühzeitig einen Mehrwert zu schaffen, aus der Praxis zu lernen und die Komplexität schrittweise und kontrolliert zu steigern.



* **Phase 1 (Minimal Viable Product - MVP):**
    * Fokus auf den **einmaligen (statischen) Feedback-Modus**.
    * Implementierung der Kernarchitektur: Supabase-Schema (ohne komplexe Sessions), Zwei-Schritt-Prompting-Kette in DSPy mit dspy.Predict.
    * Umsetzung der lehrerseitigen Konfiguration für Feedback-Fokusbereiche.
    * Ziel: Schnelle Bereitstellung einer stabilen Basisfunktionalität für einfache Aufgabentypen.
* **Phase 2 (Interaktiver Modus & Schüler-Kontrolle):**
    * Einführung des **interaktiven Dialog-Modus**.
    * Erweiterung des Datenbankschemas um feedback_sessions und feedback_messages.
    * Implementierung der schülerseitigen UI-Elemente zur Steuerung von Feedback-Aspekt und -Granularität.
    * Ziel: Ermöglichung eines echten formativen Dialogs und Stärkung der Schülerautonomie.
* **Phase 3 (Erweiterte Kontextualisierung & Lehrer-Assistenz):**
    * Entwicklung und Integration der **RAG-light-Pipeline** für den Umgang mit externen Lernmaterialien.
    * Implementierung der **optionalen, API-basierten Assistenzfunktionen** für Lehrkräfte (z.B. Rubrik-Generator).
    * Ziel: Maximierung der Feedback-Qualität durch besseres Grounding und signifikante Entlastung der Lehrkräfte im Vorbereitungsprozess.
* **Laufender Prozess (Kontinuierliche Optimierung):**
    * Von Beginn an: Aufbau des **"Gold-Standard"-Datensatzes** durch Sammeln und Validieren exzellenter Feedback-Beispiele.
    * Nach Phase 2: Beginn der regelmäßigen Optimierungszyklen mit **DSPy-Telepromptern** (BootstrapFewShot), um die Prompt-Effektivität kontinuierlich und algorithmisch zu verbessern.

Dieser gestufte Weg stellt sicher, dass GUSTAV auf einem soliden Fundament aufgebaut wird, das pädagogische Wirksamkeit, technische Stabilität und verantwortungsvollen Umgang mit KI in den Mittelpunkt stellt.


#### Referenzen



1. Application of the Hattie and Timperley Power of Feedback Model with graduate teacher education students - Digital Commons @ USF - University of South Florida, Zugriff am Juli 25, 2025, [https://digitalcommons.usf.edu/cgi/viewcontent.cgi?article=1301&context=m3publishing](https://digitalcommons.usf.edu/cgi/viewcontent.cgi?article=1301&context=m3publishing)
2. Providing Educational Feedback - ScholarBlogs, Zugriff am Juli 25, 2025, [https://scholarblogs.emory.edu/digitalmatters/files/2019/08/ProvidingEducationalFeedback.pdf](https://scholarblogs.emory.edu/digitalmatters/files/2019/08/ProvidingEducationalFeedback.pdf)
3. A Matrix of Feedback for Learning - ERIC, Zugriff am Juli 25, 2025, [https://files.eric.ed.gov/fulltext/EJ1213749.pdf](https://files.eric.ed.gov/fulltext/EJ1213749.pdf)
4. Feedback in schools - Visible Learning, Zugriff am Juli 25, 2025, [https://www.visiblelearning.com/sites/default/files/Feedback%20article.pdf](https://www.visiblelearning.com/sites/default/files/Feedback%20article.pdf)
5. Evaluating the Sensitivity of LLMs to Prior Context - arXiv, Zugriff am Juli 25, 2025, [https://arxiv.org/html/2506.00069v1](https://arxiv.org/html/2506.00069v1)
6. I believe we're at a point where context is the main thing to improve on. - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1kotssm/i_believe_were_at_a_point_where_context_is_the/](https://www.reddit.com/r/LocalLLaMA/comments/1kotssm/i_believe_were_at_a_point_where_context_is_the/)
7. What are your use cases for small (1-3-8B) models? : r/LocalLLaMA - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/1ivgqhe/what_are_your_use_cases_for_small_138b_models/](https://www.reddit.com/r/LocalLLaMA/comments/1ivgqhe/what_are_your_use_cases_for_small_138b_models/)
8. 5 Reasons Why Immediate Feedback is Important for Effective Learning - InteDashboard, Zugriff am Juli 25, 2025, [https://www.blog.intedashboard.com/blogs/tbl-learning/immediate-feedback](https://www.blog.intedashboard.com/blogs/tbl-learning/immediate-feedback)
9. Taking Education to the Next Level: The Benefits of Interactive Teaching - Kitaboo, Zugriff am Juli 25, 2025, [https://kitaboo.com/interactive-teaching/](https://kitaboo.com/interactive-teaching/)
10. Dynamic Learning v. Static Learning (DO THIS, NOT THAT) - Shake Up Learning, Zugriff am Juli 25, 2025, [https://shakeuplearning.com/blog/dynamic-learning-v-static-learning-not/](https://shakeuplearning.com/blog/dynamic-learning-v-static-learning-not/)
11. Scaffolding Language Learning via Multi-modal Tutoring Systems with Pedagogical Instructions - arXiv, Zugriff am Juli 25, 2025, [https://arxiv.org/html/2404.03429v1](https://arxiv.org/html/2404.03429v1)
12. Measuring actual learning versus feeling of learning in response to ..., Zugriff am Juli 25, 2025, [https://www.pnas.org/doi/10.1073/pnas.1821936116](https://www.pnas.org/doi/10.1073/pnas.1821936116)
13. Why Student Success Depends On Continuous Feedback - Harvard Business Publishing, Zugriff am Juli 25, 2025, [https://hbsp.harvard.edu/inspiring-minds/why-student-success-depends-on-continuous-feedback](https://hbsp.harvard.edu/inspiring-minds/why-student-success-depends-on-continuous-feedback)
14. Conversation history | Dialogflow CX - Google Cloud, Zugriff am Juli 25, 2025, [https://cloud.google.com/dialogflow/cx/docs/concept/conversation-history](https://cloud.google.com/dialogflow/cx/docs/concept/conversation-history)
15. (Part 2) Build a Conversational RAG with Mistral-7B and LangChain | by Madhav Thaker, Zugriff am Juli 25, 2025, [https://medium.com/@thakermadhav/part-2-build-a-conversational-rag-with-langchain-and-mistral-7b-6a4ebe497185](https://medium.com/@thakermadhav/part-2-build-a-conversational-rag-with-langchain-and-mistral-7b-6a4ebe497185)
16. Building Stateful Conversations with Postgres and LLMs | by Levi Stringer | Medium, Zugriff am Juli 25, 2025, [https://medium.com/@levi_stringer/building-stateful-conversations-with-postgres-and-llms-e6bb2a5ff73e](https://medium.com/@levi_stringer/building-stateful-conversations-with-postgres-and-llms-e6bb2a5ff73e)
17. Database Schema for Private Chat and Group Chat - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/Database/comments/wvrpc4/database_schema_for_private_chat_and_group_chat/](https://www.reddit.com/r/Database/comments/wvrpc4/database_schema_for_private_chat_and_group_chat/)
18. How to Design an LMS: Best Practices and Trends - Anyforsoft, Zugriff am Juli 25, 2025, [https://anyforsoft.com/blog/lms-design/](https://anyforsoft.com/blog/lms-design/)
19. LMS UI/UX Design: How to Build a Clear & Modern User Interface - Riseapps, Zugriff am Juli 25, 2025, [https://riseapps.co/lms-ui-ux-design/](https://riseapps.co/lms-ui-ux-design/)
20. Cognitive load theory in practice - Examples for the classroom - NSW Department of Education, Zugriff am Juli 25, 2025, [https://education.nsw.gov.au/content/dam/main-education/about-us/educational-data/cese/2017-cognitive-load-theory-practice-guide.pdf](https://education.nsw.gov.au/content/dam/main-education/about-us/educational-data/cese/2017-cognitive-load-theory-practice-guide.pdf)
21. The Application of Cognitive Load Theory to the Design of Health and Behavior Change Programs: Principles and Recommendations - PubMed Central, Zugriff am Juli 25, 2025, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12246501/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12246501/)
22. An introduction to cognitive load theory - The Education Hub, Zugriff am Juli 25, 2025, [https://theeducationhub.org.nz/an-introduction-to-cognitive-load-theory/](https://theeducationhub.org.nz/an-introduction-to-cognitive-load-theory/)
23. Cognitive Load Theory - The Decision Lab, Zugriff am Juli 25, 2025, [https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory](https://thedecisionlab.com/reference-guide/psychology/cognitive-load-theory)
24. How to use Cognitive Load Theory with students with SEND | InnerDrive, Zugriff am Juli 25, 2025, [https://www.innerdrive.co.uk/blog/cognitive-load-theory-send/](https://www.innerdrive.co.uk/blog/cognitive-load-theory-send/)
25. Six Strategies You May Not Be Using To Reduce Cognitive Load - The eLearning Coach, Zugriff am Juli 25, 2025, [https://theelearningcoach.com/learning/reduce-cognitive-load/](https://theelearningcoach.com/learning/reduce-cognitive-load/)
26. Complete Guide to Student-Centered vs. Teacher-Centered Learning - University of San Diego Online Degrees, Zugriff am Juli 25, 2025, [https://onlinedegrees.sandiego.edu/teacher-centered-vs-student-centered-learning/](https://onlinedegrees.sandiego.edu/teacher-centered-vs-student-centered-learning/)
27. What are the main features that differentiate between the pupil-centered teaching and the teacher-centered teaching? - Quora, Zugriff am Juli 25, 2025, [https://www.quora.com/What-are-the-main-features-that-differentiate-between-the-pupil-centered-teaching-and-the-teacher-centered-teaching](https://www.quora.com/What-are-the-main-features-that-differentiate-between-the-pupil-centered-teaching-and-the-teacher-centered-teaching)
28. Learning-Focused Feedback - Universally Designed, Zugriff am Juli 25, 2025, [https://universallydesigned.education/learning-focused-feedback/](https://universallydesigned.education/learning-focused-feedback/)
29. Teacher-Centered Versus Student-Centered Learning, Zugriff am Juli 25, 2025, [https://www.studentcenteredworld.com/teacher-centered-versus-student-centered/](https://www.studentcenteredworld.com/teacher-centered-versus-student-centered/)
30. Teacher-centered vs Student centered = A Tired & False Dichotomy : r/teaching - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/teaching/comments/19bsobd/teachercentered_vs_student_centered_a_tired_false/](https://www.reddit.com/r/teaching/comments/19bsobd/teachercentered_vs_student_centered_a_tired_false/)
31. 7 Tips To Reduce Cognitive Overload In eLearning, Zugriff am Juli 25, 2025, [https://elearningindustry.com/7-tips-reduce-cognitive-overload-elearning](https://elearningindustry.com/7-tips-reduce-cognitive-overload-elearning)
32. Teaching Young Students How to Overcome Cognitive Overload - Edutopia, Zugriff am Juli 25, 2025, [https://www.edutopia.org/article/cognitive-overload-elementary-school/](https://www.edutopia.org/article/cognitive-overload-elementary-school/)
33. Configure assignment methods and rules for queues - Learn Microsoft, Zugriff am Juli 25, 2025, [https://learn.microsoft.com/en-us/dynamics365/customer-service/administer/configure-assignment-rules](https://learn.microsoft.com/en-us/dynamics365/customer-service/administer/configure-assignment-rules)
34. Automated Feedback | Setting up in Assignment Review - FeedbackFruits, Zugriff am Juli 25, 2025, [https://help.feedbackfruits.com/hc/en-us/articles/23527132384658](https://help.feedbackfruits.com/hc/en-us/articles/23527132384658)
35. Assignment Settings 4.1 - CTL Faculty Support - MacEwan Help Centre, Zugriff am Juli 25, 2025, [https://helpcentre.macewan.ca/space/ETS/1813743184/Assignment+Settings+4.1](https://helpcentre.macewan.ca/space/ETS/1813743184/Assignment+Settings+4.1)
36. Real-Time Feedback Techniques for LLM Optimization - Ghost, Zugriff am Juli 25, 2025, [https://latitude-blog.ghost.io/blog/real-time-feedback-techniques-for-llm-optimization/](https://latitude-blog.ghost.io/blog/real-time-feedback-techniques-for-llm-optimization/)
37. Unveiling Context-Aware Criteria in Self-Assessing LLMs - arXiv, Zugriff am Juli 25, 2025, [https://arxiv.org/html/2410.21545v1](https://arxiv.org/html/2410.21545v1)
38. Local LLM Guide: RAG Implementation on Industrial Hardware | OnLogic, Zugriff am Juli 25, 2025, [https://www.onlogic.com/blog/local-llm-guide/](https://www.onlogic.com/blog/local-llm-guide/)
39. A light-weight no-cost implementation of web based Retrieval-Augmented Generation | by Anthony Demeusy | Medium, Zugriff am Juli 25, 2025, [https://medium.com/@anthony.demeusy/a-light-weight-no-cost-implementation-of-web-based-retrieval-augmented-generation-548a898ed313](https://medium.com/@anthony.demeusy/a-light-weight-no-cost-implementation-of-web-based-retrieval-augmented-generation-548a898ed313)
40. Based on your experience what is the smallest and optimal local model for RAG? - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/LocalLLaMA/comments/18q9xva/based_on_your_experience_what_is_the_smallest_and/](https://www.reddit.com/r/LocalLLaMA/comments/18q9xva/based_on_your_experience_what_is_the_smallest_and/)
41. RAG With Llama 3.1 8B, Ollama, and Langchain: Tutorial - DataCamp, Zugriff am Juli 25, 2025, [https://www.datacamp.com/tutorial/llama-3-1-rag](https://www.datacamp.com/tutorial/llama-3-1-rag)
42. Mastering Multi-Stage Prompt Structures: 5 Essential Tips | White Beard Strategies, Zugriff am Juli 25, 2025, [https://whitebeardstrategies.com/blog/mastering-multi-stage-prompt-structures-5-essential-tips/](https://whitebeardstrategies.com/blog/mastering-multi-stage-prompt-structures-5-essential-tips/)
43. How to Use Prompt Engineering Techniques for Deep Inquiry, Creative Mapping, and Strategic Insight with ChatGPT : r/ChatGPTPromptGenius - Reddit, Zugriff am Juli 25, 2025, [https://www.reddit.com/r/ChatGPTPromptGenius/comments/1k6naun/how_to_use_prompt_engineering_techniques_for_deep/](https://www.reddit.com/r/ChatGPTPromptGenius/comments/1k6naun/how_to_use_prompt_engineering_techniques_for_deep/)
44. LLMOps with DSPy: Build RAG Systems Using Declarative Programming - PyImageSearch, Zugriff am Juli 25, 2025, [https://pyimagesearch.com/2024/09/09/llmops-with-dspy-build-rag-systems-using-declarative-programming/](https://pyimagesearch.com/2024/09/09/llmops-with-dspy-build-rag-systems-using-declarative-programming/)
45. DSPy | Clio AI Deep Dive, Zugriff am Juli 25, 2025, [https://www.clioapp.ai/deep-dives/dspy](https://www.clioapp.ai/deep-dives/dspy)
46. Programming, Not Prompting: A Hands-On Guide to DSPy | Towards Data Science, Zugriff am Juli 25, 2025, [https://towardsdatascience.com/programming-not-prompting-a-hands-on-guide-to-dspy/](https://towardsdatascience.com/programming-not-prompting-a-hands-on-guide-to-dspy/)
47. An Exploratory Tour of DSPy: A Framework for Programing Language Models, not Prompting | by Jules S. Damji | The Modern Scientist | Medium, Zugriff am Juli 25, 2025, [https://medium.com/the-modern-scientist/an-exploratory-tour-of-dspy-a-framework-for-programing-language-models-not-prompting-711bc4a56376](https://medium.com/the-modern-scientist/an-exploratory-tour-of-dspy-a-framework-for-programing-language-models-not-prompting-711bc4a56376)
48. Easiest Tutorial to Learn DSPy with LLM Example - YouTube, Zugriff am Juli 25, 2025, [https://www.youtube.com/watch?v=Jfpxjg8xj9w](https://www.youtube.com/watch?v=Jfpxjg8xj9w)
49. Automated assignment grading with large language models: insights from a bioinformatics course - Oxford Academic, Zugriff am Juli 25, 2025, [https://academic.oup.com/bioinformatics/article/41/Supplement_1/i21/8199383](https://academic.oup.com/bioinformatics/article/41/Supplement_1/i21/8199383)
50. Grading Massive Open Online Courses Using Large Language Models - ACL Anthology, Zugriff am Juli 25, 2025, [https://aclanthology.org/2025.coling-main.263.pdf](https://aclanthology.org/2025.coling-main.263.pdf)
51. How Teachers Can Use AI in the Classroom for Lesson Planning, Zugriff am Juli 25, 2025, [https://www.maryvilleca2.com/post/how-teachers-can-use-ai-for-lesson-planning](https://www.maryvilleca2.com/post/how-teachers-can-use-ai-for-lesson-planning)
52. GDPR and Google Cloud, Zugriff am Juli 25, 2025, [https://cloud.google.com/privacy/gdpr](https://cloud.google.com/privacy/gdpr)
53. Large language models (LLM) | European Data Protection Supervisor, Zugriff am Juli 25, 2025, [https://www.edps.europa.eu/data-protection/technology-monitoring/techsonar/large-language-models-llm_en](https://www.edps.europa.eu/data-protection/technology-monitoring/techsonar/large-language-models-llm_en)
54. Data security and privacy precautions for Using Third-Party LLM APIs in Enterprise, Zugriff am Juli 25, 2025, [https://www.rohan-paul.com/p/data-security-and-privacy-precautions](https://www.rohan-paul.com/p/data-security-and-privacy-precautions)
55. TeachMateAI, Zugriff am Juli 25, 2025, [https://teachmateai.com/](https://teachmateai.com/)
56. Free, AI-powered teacher assistant by Khan Academy - Khanmigo, Zugriff am Juli 25, 2025, [https://www.khanmigo.ai/teachers](https://www.khanmigo.ai/teachers)
57. Risks of Generative Artificial Intelligence in Higher Education: A critical perspective - International Journal of Advances in Engineering and Management ( IJAEM ), Zugriff am Juli 25, 2025, [https://ijaem.net/issue_dcp/Risks%20of%20Generative%20Artificial%20Intelligence%20in%20Higher%20Education%20A%20critical%20perspective.pdf](https://ijaem.net/issue_dcp/Risks%20of%20Generative%20Artificial%20Intelligence%20in%20Higher%20Education%20A%20critical%20perspective.pdf)
58. LLM Hallucination Detection and Mitigation: Best Techniques - Deepchecks, Zugriff am Juli 25, 2025, [https://www.deepchecks.com/llm-hallucination-detection-and-mitigation-best-techniques/](https://www.deepchecks.com/llm-hallucination-detection-and-mitigation-best-techniques/)
59. The Beginner's Guide to Hallucinations in Large Language Models | Lakera – Protecting AI teams that disrupt the world., Zugriff am Juli 25, 2025, [https://www.lakera.ai/blog/guide-to-hallucinations-in-large-language-models](https://www.lakera.ai/blog/guide-to-hallucinations-in-large-language-models)
60. Student Perspectives on the Benefits and Risks of AI in Education - arXiv, Zugriff am Juli 25, 2025, [https://arxiv.org/html/2505.02198v1](https://arxiv.org/html/2505.02198v1)
61. How to Prevent the Misuse of AI in Education - TAO Testing, Zugriff am Juli 25, 2025, [https://www.taotesting.com/blog/misuse-of-ai-in-education/](https://www.taotesting.com/blog/misuse-of-ai-in-education/)
62. Guide: How Professors Can Discourage and Prevent AI Misuse, Zugriff am Juli 25, 2025, [https://automatedteach.com/p/guide-professors-discourage-prevent-ai-misuse](https://automatedteach.com/p/guide-professors-discourage-prevent-ai-misuse)
63. Using AI to address common challenges in student feedback - SchoolAI, Zugriff am Juli 25, 2025, [https://schoolai.com/blog/using-ai-address-common-challenges-student-feedback](https://schoolai.com/blog/using-ai-address-common-challenges-student-feedback)
64. Hallucinations in LLMs: Can You Even Measure the Problem? - Medium, Zugriff am Juli 25, 2025, [https://medium.com/google-cloud/hallucination-detection-measurement-932e23b1873b](https://medium.com/google-cloud/hallucination-detection-measurement-932e23b1873b)
65. From Detection to Prevention: How to Discourage AI Misuse in Academia, Zugriff am Juli 25, 2025, [https://detecting-ai.com/blog/from-detection-to-prevention-how-to-discourage-ai-misuse-in-academia](https://detecting-ai.com/blog/from-detection-to-prevention-how-to-discourage-ai-misuse-in-academia)
66. How can I Revise my Assignments to Deter Student use of AI? | Office of Digital Learning | University of Nevada, Reno, Zugriff am Juli 25, 2025, [https://www.unr.edu/digital-learning/instructional-strategies/understanding-and-integrating-generative-ai-in-teaching/how-can-i-revise-my-assignments-to-deter-student-use-of-ai](https://www.unr.edu/digital-learning/instructional-strategies/understanding-and-integrating-generative-ai-in-teaching/how-can-i-revise-my-assignments-to-deter-student-use-of-ai)
