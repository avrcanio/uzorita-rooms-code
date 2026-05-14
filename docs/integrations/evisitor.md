# eVisitor — globalni flow (MVP)

**Owner:** TBD
**Last updated:** 2026-02-13
**Status:** Draft

## Cilj
Nakon potvrđenog check-ina (Confirm/Submit), sustav **automatski** šalje prijavu boravka u eVisitor (HR) i recepciji jasno pokaže je li prijava **poslana i primljena** (ack).

## Kada se šalje
- automatski odmah nakon Confirm/Submit u check-in wizardu
- kad se kasnije doda dodatni gost: automatski slanje i za tog gosta (po potrebi)

## Flow (globalno)
1) Check-in završen (glavni gost potvrđen)
2) Sustav postavi status: eVisitor PENDING
3) Sustav pošalje prijavu u eVisitor
4) Sustav primi odgovor (ack)
5) Rezultat:
   - SENT (primljeno/OK) → označi prijavljeno + spremi identifikator/potvrdu ako postoji
   - FAILED → označi grešku + omogućiti retry

## Statusi
- PENDING
- SENT (poslano i primljeno)
- FAILED

## UI (recepcija)
Na detalju rezervacije:
- Timeline event: eVisitor PENDING / SENT / FAILED
- Badge uz **glavnog gosta**: PENDING / SENT / FAILED (brzo vidljivo stanje)

## Podaci (iz OCR + ručno potvrđenih polja)
Koristimo širi set koji skupljamo:
- ime, prezime, spol, datum rođenja, državljanstvo
- tip dokumenta, broj dokumenta
- datum izdavanja, datum isteka
- mjesto rođenja, adresa (ako treba/ako postoji)
- OIB (ako postoji / ručno)

## Audit
- bilježimo svaki pokušaj slanja (vrijeme, korisnik, rezultat, poruka)
- spremamo request/response payload (bez slika osobnih)

## Napomena
Detalji protokola/autentikacije eVisitor implementiraju se tijekom kodiranja prema službenoj specifikaciji i pristupu.

## Implementacijski checklist (trenutno stanje)

### A) Preduvjeti i pristup eVisitor API-ju
- [ ] Produkcijski eVisitor API pristupni podaci (username/password) su zaprimljeni.
- [ ] Testni eVisitor API pristupni podaci su zaprimljeni.
- [ ] Definirane env varijable za eVisitor (`base_url`, `username`, `password`, `apikey` za test).
- [ ] Implementiran login/logout client (cookie-based auth) prema eVisitor pravilima.
- [ ] Implementiran health/probe za eVisitor dostupnost i auth.

### B) Podaci gosta za prijavu (CheckInTourist)
- [x] Ime i prezime (`TouristName`, `TouristSurname`) postoje u modelu.
- [x] Spol (`Gender`) postoji u modelu.
- [x] Datum rođenja (`DateOfBirth`) postoji u modelu.
- [x] Državljanstvo (`Citizenship`) postoji u modelu (trenutno kao ISO2, potrebno mapiranje na ISO3).
- [x] Broj dokumenta (`DocumentNumber`) postoji u modelu.
- [x] Tip dokumenta (`DocumentType`) postoji u modelu.
- [x] Datum izdavanja i isteka dokumenta postoje u modelu.
- [x] OIB / personal ID postoji u modelu (`personal_id_number`).
- [ ] Država rođenja (`CountryOfBirth`, ISO3) ima dedicated polje i mapiranje.
- [ ] Mjesto rođenja (`CityOfBirth`) ima dedicated polje i mapiranje.
- [ ] Država prebivališta (`CountryOfResidence`, ISO3) ima dedicated polje i mapiranje.
- [ ] Kontakt podaci gosta (`TouristEmail`, `TouristTelephone`) su modelirani i validirani.

### C) Podaci rezervacije/objekta
- [x] Datumi boravka postoje (`check_in_date`, `check_out_date`).
- [ ] eVisitor `Facility` sifra objekta je spremljena i mapirana po smjestaju.
- [ ] `TTPayerID`/kontekst obveznika je modeliran (ako je potreban po roli).
- [ ] Pravila za dodatne uvjetne podatke (npr. granicni prijelaz/passagedate) su definirana.

### D) Integracijski sloj (backend)
- [ ] Implementiran service za `CheckInTourist` akciju.
- [ ] Implementiran service za `CheckOutTourist` akciju.
- [ ] Implementiran service za `CancelTouristCheckIn` akciju.
- [ ] Implementirana idempotencija (ponovni pozivi ne stvaraju duple prijave).
- [ ] Implementiran retry mehanizam za privremene greske.
- [ ] Spremamo eVisitor povratni `ID` prijave za kasniju izmjenu/odjavu.

### E) Statusi i UI
- [ ] Statusi eVisitor sinka su modelirani (`PENDING`, `SENT`, `FAILED`).
- [ ] Timeline prikazuje eVisitor evente/status.
- [ ] Guest/reservation detail prikazuje badge statusa.
- [ ] UI podrzava ručni retry neuspjele prijave.

### F) Audit, sigurnost i usklađenost
- [x] OCR audit postoji (`OcrScanLog`) kao temelj za trag obrade podataka.
- [ ] eVisitor audit log postoji (request/response, timestamp, user, rezultat).
- [ ] Osjetljivi podaci u logovima su minimizirani/maskirani po pravilima.
- [ ] Definirana retention politika za eVisitor payload i logove.

### G) Šifrarnici i mapiranja
- [ ] Automatiziran dohvat i cache eVisitor šifrarnika (`Country`, `DocumentType`, ostali lookupi).
- [ ] Mapiranje `nationality` ISO2 -> ISO3 je implementirano i testirano.
- [ ] Mapiranje naših tipova dokumenata na eVisitor `DocumentType` CODE je implementirano.
- [ ] Validacija obaveznih polja prije slanja (`CheckInTourist`) je implementirana.

### H) Trenutno imamo implementirano (sa strane OCR ingest-a)
- [x] Microblink skeniranje dokumenta u frontend-u.
- [x] OCR payload ingest endpoint u backend-u.
- [x] Auto-popunjavanje prosirenih `Guest` polja nakon OCR-a.
- [x] Ručna korekcija gost podataka kroz guest detail ekran.
- [x] OCR provider standardiziran na `microblink` (PassportEye izbacen iz aktivnog flowa).
- [ ] eVisitor slanje jos nije implementirano.


upute evisitor
Web API
Print
RSS
Modified on 03.04.2023. 03:17:PM by htz.ibegovic
Categorized as WEB API
Table of Contents [Hide/Show]


   Korištenje e-Visitor Web API funkcionalnosti
      Prijava (login) na e-Visitor Web API
   Pristup testnoj okolini
   Vrste REST resursa
      Entity
      Browse
      Action
   Često korišteni procesi
      Prijava turista
      Odjava turista
      Izmjena prijave turista
      Poništanje prijave turista
      Otvaranje novog obveznika
      Pregled postojećih obveznika
      Aktivacija postojećeg obveznika u "svojoj" turističkoj zajednici
      Otvaranje novog objekta
      Deaktivacija objekta
      Kreiranje datoteke za MUP
      Unos gotovinske uplate
      Dohvat podataka za ispis 3 uplatnice za paušaliste
      Pokretanje okvirnog obračuna
      Unos DZS podataka za objekt
      Dohvat ID podatka za objekt
   Resursi
      Akcije
      Entiteti
      Browse
    !!! NOVO !!! Upute za dodijelu pristupnih podataka
    !!! NOVO !!!
    !!! NOVO 2022 !!!
   Povezane stranice


Korištenje e-Visitor Web API funkcionalnosti¶
Sučelje je izvedeno kao REST service (root URI: https://www.evisitor.hr/eVisitorRhetos_API/Rest/). Kroz eVisitor Web API sučelje moguće je izvršiti sve operacije koje su dostupne kroz web sučelje same eVisitor aplikacije, pri čemu vrijede ista sigurnosna i poslovna pravila. Primjeri korištenja biti će prikazani u C# programskom jeziku koristeći RestSharp REST klijent. Dozvoljene vrijednosti šifrarnika korištenih u pozivima metoda dostupne su na wiki stranici e-Visitora - Web API - Lista šifrarnika. 

Svi parametri za rest pozive se šalju u JSON formatu. Datumi se šalju u .NET json Date formatu ("\/Date(1426028400000+0100)\/"), osim ako nije drugačije specificirano za određeni resurs.

Za pregled novosti u pojedinim verzijama REST-a posjetite stranicu WEB API - Novosti

Prijava (login) na e-Visitor Web API¶
Da bi pristup API-ju bio dozvoljen potrebno se prijaviti (login) u sustav koristeći Authentication service API (URI: https://www.evisitor.hr/eVisitorRhetos_API/Resources/AspNetFormsAuth/Authentication/), koji implementira slijedeće metode:

Login
Interface: (string UserName, string Password, string apikey, bool PersistCookie) -> bool
Primjer request data: {"userName": "username";"password": "pass"; "apikey": apikey"} *(remark) API ključ se trenutno koristi samo na testnoj platformi
Ukoliko se pošalje bez API ključa vraća grešku: {"UserMessage": null, "SystemMessage": "Application is not registered or is deactivated or API key has expired."}
Odgovor je true pri uspješnom loginu, inače false. Pri uspješnom loginu odgovor servera sadrži i niz cookie-a (authentication, affinity, language) koji se moraju slati prilikom svakog poziva API REST servisa.
Logout
Nema nikakvih parametara, potrebno je proslijediti dobivene cookie-e. Odgovor je prazan.



Primjer prijave na sustav se nalazi u datoteci Authentication.cs, u prilogu Htz.eVisitor.WebApi.Test.zip. Primjer za PHP nalazi se u prilogu eVisitor.PHP.zip.

Pristupni podaci u primjeru su samo ogledni. Ukoliko želite pristupiti sustavu eVisitor, obratite se korisniku za kojeg programirate informacijski sustav.

Pristup testnoj okolini¶
Aplikacija - https://www.evisitor.hr/test
API ROOT URL - https://www.evisitor.hr/testApi - za login se poziva metoda https://www.evisitor.hr/testApi/Resources/AspNetFormsAuth/Authentication/Login a za ostale resurse sukladno tome npr. https://www.evisitor.hr/testApi/Rest/Htz/Country/

Podaci u testnoj okolini su snapshot podataka iz produkcije od 09.12 - nikakve promjene u produkciji nakon 09.12 se ne vide u testu i obrnuto. To znači da za testnu okolinu treba tražiti zasebne pristupne podatke. Također ne preporuča se koristiti istu kombinaciju korisničkog imena i lozinke za obje okoline.

Vrste REST resursa¶
U ovom poglavlju biti će objašnjene sve dostupne vrste REST resursa. Svi konkretni resursi biti će definirani vrstom i specifičnim informacijama za pojedinu vrstu resursa.

Entity¶
Ovaj resurs podržava čitanje, unos, izmjenu i brisanje podataka. Neki od entity resursa ne podržavaju direktnu izmjenu podataka zbog svoje složenosti i ovisnosti o drugim resursima. Njihova izmjena je podržana posebnim metodama(Action-ima). Entity resurs biti će opisan relativnim path-om, popisom atributa, http metoda, te parametrima metoda. Primjer opisa jednog entiteta:

County

Path: Htz/County
Atributi:
ID (guid)
Name (string)
OrdinalNumber (int)
ClusterCountyID (guid)

Entity resurs podržava slijedeće metode:

GET - dohvat podataka
Parametri:
page - broj stranice koji se želi dohvatiti
psize - broj zapisa po stranici
sort - atribut (ili više njih odvojeni zarezom) po kojem se dohvat sortira (dodaci asc i desc označuju način srotiranja).
filters - popis uvjeta filtranja. Svaki uvjet mora sadržavati tri podatka: Property, Operation i Value. Podržane su slijedeće operacije: equal, notequal, greater, greaterequal, less, lessequal, startswith, contains, datein (podržanost operacija ovisi o tipu podataka)
Rezultat:{Records:[]}
primjer poziva metode:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/Country/?psize=20&page=1&filters=[{"Property":"Active","Operation":"equal","Value":"true"},{"Property":"CodeTwoLetters","Operation":"startswith","Value":"a"}]&sort=NameNational%20desc
Uz svaku GET metodu podržana je i metoda TotalRecordsAndCount (entityPath/TotalRecordsAndCount) koja u rezultatu uz Records vraća i TotalCount, te metoda TotalCount koja vraća samo TotalCount. Obje metode podržavaju iste parametre kao i GET metoda. Slijedi primjer poziva RecordsAndTotalCount metode:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/Country/RecordsAndTotalCount?psize=20&page=1&sort=NameNational%20desc
primjer poziva metode za dohvat određenog zapisa:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/Country/e6229d5e-cccc-4477-8206-9f17f95f54b1


POST - unos novog zapisa
Parametri: kao parametar http requesta potrebno je poslati JSON serijaliziranu instancu novog zapisa
Rezultat: {ID} id (guid) novog zapisa ukoliko je zapis uspješno snimljen. Ukoliko je došlo do greške tada metoda vraća JSON {SystemMessage, UserMessage} koji sadrže sistemske odnosno validacijske greške zbog kojih snimanje nije uspjelo.

PUT - izmjena zapisa
na path entiteta potrebno je dodati i njegov id (npr. https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/Country/e6229d5e-cccc-4477-8206-9f17f95f54b1)
Parametri: kao parametar http requesta potrebno je poslati JSON serijaliziranu instancu zapisa. Potrebno je slati sve podatke, a ne samo one koje želite izmjeniti.
Rezultat: prazan ukoliko je zapis uspješno snimljen. Ukoliko je došlo do greške tada metoda vraća JSON {SystemMessage, UserMessage} koji sadrže sistemske odnosno validacijske greške zbog kojih snimanje nije uspjelo.

DELETE - brisanje zapisa
na path entiteta potrebno je dodati i njegov id (npr. https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/Country/e6229d5e-cccc-4477-8206-9f17f95f54b1)
Parametri: nema parametara
Rezultat: prazan ukoliko je zapis uspješno obrisan. Ukoliko je došlo do greške tada metoda vraća JSON {SystemMessage, UserMessage} koji sadrže sistemske odnosno validacijske greške zbog kojih snimanje nije uspjelo.



Browse¶
Ovaj resurs podržava čitanje podataka iz entiteta u specifičnom obliku. Metoda koju podržava je GET čiji interface je identičan interface-u GET metode opisanom u Entity resursu.

Action¶
Ovaj resurs podržava izvršavanje serverske akcije. Metoda koju podržava je POST. Parametar se šalje serijaliziran u JSON i specifičan je za konkretnu akciju. Rezultat je prazan u slučaju uspješnog izvršavanja, inače sadrži grešku zbog kojeg izvršavanje nije uspjelo.

Često korišteni procesi¶
Prijava turista¶
Da bi prijavili turista potrebno je pozvati akciju CheckInTourist. Akcija ImportTourists još je uvijek dostupna. U prilogu stranice se nalazi testni projekt u kojem su i primjeri korištenja akcija CheckInTourist, CheckOutTourist i CancelTouristCheckIn.

Odjava turista¶
Da bi odjavili turista potrebno je pozvati akciju CheckOutTourist. Akcija ImportTouristCheckOut još je uvijek dostupna. U prilogu stranice se nalazi testni projekt u kojem su i primjeri korištenja akcija CheckInTourist, CheckOutTourist i CancelTouristCheckIn.

Izmjena prijave turista¶
Da bi izmjenili prijavu turista potrebno je pozvati akciju CheckInTourist s parametrom ID koji je proslijeđen prilikom prijave turista. Moguće je izmjeniti samo aktivne prijave. Potrebno je slati sve podatke, a ne samo one koje želite izmjeniti. U prilogu stranice se nalazi testni projekt u kojem su i primjeri korištenja akcija CheckInTourist, CheckOutTourist i CancelTouristCheckIn.

Poništanje prijave turista¶
Da bi poništili prijavu turista potrebno je pozvati akciju CancelTouristCheckIn s parametrom ID koji je proslijeđen prilikom prijave turista. U prilogu stranice se nalazi testni projekt u kojem su i primjeri korištenja akcija CheckInTourist, CheckOutTourist i CancelTouristCheckIn

Otvaranje novog obveznika¶
Da bi otvorili novog obveznika potrebno je pozvati slijedeće akcije:

UploadDocument - upload dokumenta temeljem kojeg se otvara novi obveznik
ID parametar ćete u pozivu akcije SaveTTPayer proslijediti u parametru OpeningBasisDocumentID
SaveTTPayer - osnovni podaci obveznika
SaveTTPayerAdditionalData - dodatni podaci obveznika
ID parametar pojedinih entiteta koji se prosljeđuju mora biti istovjetan onom koji je proslijeđen u pozivu SaveTTPayer akcije

Pregled postojećih obveznika¶
Za pregled postojećih obveznika koristite browse TTPayerUnion.

Aktivacija postojećeg obveznika u "svojoj" turističkoj zajednici¶
Da bi aktivirali obveznika u svojoj turističkoj zajednici potrebno je pozvati akciju AddRightsToTTPayer. Ova akcija dopuštena je samo roli "turistička zajednica". Da bi saznali da li je obveznik zaveden u sustav pozovite resurs
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/TTPayerExists/?filter=Htz.TTPayerExistsParam&fparam={Pin:"01234567890"}

Otvaranje novog objekta¶
Da bi otvorili novi objekt potrebno je pozvati slijedeće akcije:

UploadDocument - upload dokumenta temeljem kojeg se otvara novi objekt
SaveFacility - osnovni podaci objekta
SaveFacilityCharacteristics - karakteristike objekta
ID parametar mora biti istovjetan onom koji je proslijeđen u pozivu SaveFacility akcije

Sve tri akcije obvezno se moraju pozvati kako bi se ispravno otvorio objekt.
Deaktivacija objekta¶
Da bi deaktivirali objekt potrebno je pozvati slijedeće akcije:

CreateFinalCalculation - pokretanje završnog obračuna za objekt
UploadDocument - upload dokumenta temeljem kojeg se deaktivira objekt
DeactivateFacility - deaktivira objekt

Kreiranje datoteke za MUP¶
Da bi kreirali datoteku za MUP potrebno je pozvati slijedeće akcije:

CreateFileForMI - akcija koja generira dataoteku za MUP
ID parametar ćete iskoristiti prilikom dohvata datoteke u slijedećem koraku
Pozvati GET na resursu MITTPayerFiles sa id-jem koji je proslijeđen prilikom poziva akcije CreateFileForMI

Unos gotovinske uplate¶
Da bi unijeli gotovinsku uplatu (ručno zaduženje/odobrenje potrebno je pozvati akciju SaveCashDiaryPayment.

Dohvat podataka za ispis 3 uplatnice za paušaliste¶
Da bi dohvatili podatke potrebne za ispis 3 uplatnice za paušaliste koristite Browse PaymentFlatRateSlipSample.

Pokretanje okvirnog obračuna¶
Pokretanje okvirnog obračuna i dohvat podataka obračuna sastoji se od slijedećih koraka:
Pozovite akciju SaveTuristiZaObracunBoravisnePristojbeTemp, s time da zapamtite vrijednost IDTTCalculationTemp koju proslijeđujete jer ćete nju koristiti za dohvat rezultata obračuna
Pozovite akciju CalculateTTTemp, s time da proslijedite vrijednost IDTTCalculationTemp iz prethodnog koraka
Za dohvat podataka obračuna po turistima koristite browse TTCalculationItemSourceByTourist filtriran po IDTTCalculationTemp
Za dohvat podataka s detaljima obračuna za pojedinog turista koristite browse TTCalculationItemSourceTempBrowse filtriran po IDTTCalculationTemp i TouristID
Za dohvat podataka obračuna po objektima koristite browse TTCalculationItemSourceByFacility filtriran po IDTTCalculationTemp

Unos DZS podataka za objekt¶
Da bi unijeli podatke potrebne za DZS koristite POST metodu entiteta FacilityNsoData.

Dohvat ID podatka za objekt¶
Da bi dohvatili ID objekta potrebno je pozvati GET metodu browse-a FacilityBrowse sa filterom po Code atributu. Primjer poziva metode:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/FacilityBrowse/?filters=[{"Property":"Code","Operation":"equal","Value":"123456"}]

Resursi¶
Akcije¶
AddRightsToTTPayer
Path: Htz/AddRightsToTTPayer/
Atributi:
FirstName (string) - obavezan podatak ako je IsNaturalPerson=true, ime obveznika
IsNaturalPerson (bool) - obavezan podatak, da li je obveznik fizička osoba
Pin (string) - obavezan podatak, OIB obveznika
Surname (string) - obavezan podatak ako je IsNaturalPerson=true, prezime obveznika
Greške koje akcija vraća:
Ne postoji obveznik sa zadanim OIB-om. - javlja se ako ne postoji obveznik sa zadanim OIB-om
Ne možete prijaviti obveznika jer je deaktiviran. - javlja se ako je obveznik sa zadanim OIB-om deaktiviran
Unijeli ste OIB pravne osobe. Ne može se otvoriti obveznik. - javlja se ako je obveznik sa zadanim OIB-om pravna osoba, a u akciji je proslijeđen parametar IsNaturalPerson=true
Unijeli ste OIB fizičke osobe. Ne može se otvoriti obveznik. - javlja se ako je obveznik sa zadanim OIB-om fizička osoba, a u akciji je proslijeđen parametar IsNaturalPerson=false
Obveznik sa zadanim OIB-om je već evidentiran u sustavu. Niste ispravno upisali ime ili prezime obveznika. - javlja se ako je obveznik fizička osoba, a proslijeđeno ime i prezime ne odgovara postojećem obvezniku sa zadanim OIB-om

CancelTouristCheckIn
Path: Htz/CancelTouristCheckIn/
Atributi:
ID (guid) - obavezan podatak, ID prijave turista
TTPayerID(guid) - obavezan podatak ako je user koji poziva akciju TZ, ako je user obveznik onda sustav sam postavlja ovaj podatak
Reason - razlog poništenja prijave

CancelTouristCheckOut
Path: Htz/CancelTouristCheckOut/
Atributi:
ID (guid) - obavezan podatak, ID prijave turista
Reason - razlog poništenja odjave

CalculateTTTemp
Path: Htz/CalculateTTTemp/
Atributi:
IDTTCalculationTemp(guid) - obavezan podatak vrijednost s kojom je pozvana akcija SaveTuristiZaObracunBoravisnePristojbeTemp

CheckInTourist
Path: Htz/CheckInTourist/
Atributi:
ID - guid, identifikator prijave turista, kasnije se koristi za identifikaciju pri izmjeni ili odjavi određene prijave turista
TTPayerID(guid) - obavezan podatak ako je user koji poziva akciju TZ, ako je user obveznik onda sustav sam postavlja ovaj podatak
AccommodationUnitType (string) - podatak nije obavezan, naziv vrste smještajne jedinice, vrijednost iz browse-a AccommodationUnitFacilityType filtriran po FacilityCode
ArrivalOrganisation - šifra (MUP) organizacije dolaska, vrijednost CodeMI iz browse-a ArrivalOrganisationLookup
TouristAgency - OIB ili VAT number turističke agencije, ukoliko je organizacija dolaska putem agencije. vrijednost iz browse-a TouristAgencyBrowse. Ukoliko ne postoji tražena agencija možete unijeti novu agenciju u sustav pomoću entity resursa TouristAgency. Neobavezan podatak ukoliko ArrivalOrganisation je "Osoban". Ukoliko je "Agencijski" onda je TuristAgency obvezan podatak.
Citizenship – tro-slovna šifra države (ISO oznaka) čije državljanstvo ima turist (npr. HRV za Hrvatsku ili DEU za Njemačku)
CityOfBirth – opcionalno; ukoliko je država rođenja Hrvatska, onda ovdje treba staviti naziv grada-naselja rođenja u obliku „grad-naselje“ iz pripremljenog šifrarnika, npr. „Zagreb-Adamovec“. Ukoliko država rođenja nije Hrvatska, onda ovdje treba biti upisan naziv grada iz te države s tim da trenutno sustav prihvaća slobodni unos
CityOfResidence - ukoliko je država prebivališta Hrvatska, onda ovdje treba staviti naziv grada-naselja prebivališta u obliku „grad-naselje“ iz pripremljenog šifrarnika, npr. „Zagreb-Adamovec“. Ukoliko država prebivališta nije Hrvatska, onda ovdje treba biti upisan naziv grada iz te države s tim da trenutno sustav prihvaća slobodni unos
CountryOfBirth – tro-slovna šifra države (ISO oznaka) rođenja (npr. HRV za Hrvatsku ili DEU za Njemačku)
CountryOfResidence – tro-slovna šifra države (ISO oznaka) prebivališta (npr. HRV za Hrvatsku ili DEU za Njemačku)
DateOfBirth - datum rođenja turista (format: YYYYMMDD, primjer 19760413)
DocumentNumber - broj isprave kojom turist potvrđuje identitet
DocumentType - šifra vrste isprave kojom turist potvrđuje identitet (Atribut CODE iz resursa DocumentTtypeLookup ili kolona Oznaka ako se gleda Excel)
Facility - šifra objekta u koji se turist prijavljuje. Šifra objekta je objektu dana od sustava e-Visitor.
ForeseenStayUntil - datum do kojeg turist predviđa boraviti u objektu (format: YYYYMMDD, primjer 20150413)
Gender - ženski/muški
IsTTFlatRatePaymentVacationHome (bool) - opcionalno; želi plaćati pristojbu paušalno; polje nije obavezno
OfferedServiceType - naziv vrste pružene usluge
ResidenceAddress - opcionalno; ulica i broj prebivališta
StayFrom - datum od kojeg turist boravi u objektu (format: YYYYMMDD, primjer 20150413)
TimeEstimatedStayUntil - vrijeme do kojeg turist predviđa boraviti u objektu (format: hh:mm, primjer 09:42)
TimeStayFrom - vrijeme od kojeg turist boravi u objektu (format: hh:mm, primjer 09:42)
TouristEmail - e-mail turista, opcionalno (podatak se validira, stoga mora biti validna email adresa)
TouristMiddleName - srednje ime turista (opcionalno)
TouristName - ime turista
TouristSurname - prezime turista
TouristTelephone - kontakt telefon turista, opcionalno (validan format: +385916655333)
TTPaymentCategory - šifra kategorije plaćanja boravišne pristojbe
Validacija podataka:
Svi podaci su obavezni osim onih koji su označeni kao neobavezni ili je navedeno poslovno pravilo kad su obavezni
Upisan datum boravka do je manji od datuma boravka od. (item.StayFrom > item.ForeseenStayUntil)
Upisano vrijeme odlaska je manje od upisanog vremena dolaska. (item.StayFrom == item.ForeseenStayUntil && item.TimeEstimatedStayUntil <= item.TimeStayFrom)
Potrebno je upisati granični prijelaz, te datum prijelaza. (item.CountryResidence.IsEUMember == false && (item.BorderCrossingHr == null || item.PassageDate == null)
Prekoračen je maksimalan broj dana boravka turista. (item.ForeseenStayUntil - item.StayFrom) > MaximumTouristsDaysOfStay)
Turist je već prijavljen u navedenom objektu. (x.Facility == item.Facility && x.DateOfBirth == item.DateOfBirth && x.DocumentTtype == item.DocumentTtype && x.DocumentNumber == item.DocumentNumber && x.CountryResidence == item.CountryResidence && item. CheckedOutTourist == false && item.TouristCancelled == false)
Nije dopušten unos datuma boravka od koji ne zadovoljava definirana prava. ( x.StayFrom <= (Today - parameters.AllowedNumberOfDaysToCheckInCheckOut))
Paušalno plaćanje dozvoljeno je samo za kuće za odmor do 15.7. u godini. (x => x.IsTTFlatRatePaymentVacationHome == true && (x.Facility.FacilitySubcategory.TTCalculationType.IsVacationHomeCalculation == false || x.StayFrom > new DateTime(DateTime.Today.Year, 7, 15)). Dohvat podatka IsTTFlatRatePaymentVacationHome moguć je iz resursa FacilityTouristCheckInLookup filtriran po ID-ju ili Code property-u objekta.
Paušalno plaćanje nije dozvoljeno za turiste koji nisu iz europskog gospodarskog pojasa. (item => item.Facility.FacilitySubcategory.TTCalculationType.IsVacationHomeCalculation == true && item.CitizenshipCountry.IsEEAMember == false && item.IsTTFlatRatePaymentVacationHome == true)
Grad rođenja nije zadan. (item => string.IsNullOrEmpty(item.CityOfBirthAbroad) && item.CityOfBirthSettlementHrID == null)
Grad prebivališta nije zadan. (item => string.IsNullOrEmpty(item.CityResidenceAbroad) && item.CityOfResidenceSettlementHrID == null)
StayFrom i TimeStayFrom podatke obveznik ne može naknadno mijenjati. TZ može mijenjati navedene podatke unutar perioda zadanih sistemskim parametrom kojeg određuje HTZ.
TTPaymentCategory mora biti dozvoljen za proslijeđeni objekt (lista dozvoljenih kategorija obračuna boravišne pristojbe moguće je dobiti iz browse-a TTPaymentCategoryLookup2, filtriran po FacitlityID)

CheckOutTourist
Path: Htz/CheckOutTourist/
Atributi:
ID (guid) - obavezan podatak, ID prijave turista
TTPayerID(guid) - obavezan podatak ako je user koji poziva akciju TZ, ako je user obveznik onda sustav sam postavlja ovaj podatak
CheckOutDate - datum odjave turista (format: YYYYMMDD, primjer 20150413)
CheckOutTime - vrijeme odjave turista (format: hh:mm, primjer 09:42)
Validacija podataka:
Svi podaci su obavezni osim onih koji su označeni kao neobavezni ili je navedeno poslovno pravilo kad su obavezni
Upisan datum odjave je manji od datuma boravka od. (item.CheckOutDate < item.StayFrom)
Datum odjave turista ne smije biti veći od današnjeg datuma. (item.CheckOutDate > Today)
Nije dopušten unos datuma odjave koji ne zadovoljava definirana prava. ( x. CheckOutDate <= (Today - parameters.AllowedNumberOfDaysToCheckInCheckOut))

CreateFileForMI
Path: Htz/CreateFileForMI/
Atributi:
ID (guid) - obavezan podatak
FileName (string) - obavezan podatak
TTPayerID (guid) - obavezan podatak ako je user koji poziva akciju TZ, ako je user obveznik onda sustav sam postavlja ovaj podatak

CreateFinalCalculation
Path: Htz/CreateFinalCalculation/
Atributi:
FacilityID (guid) - obavezan podatak, ID objekta za koji se radi završni obračun
FacilityClosingDate (date) - obavezan podatak, datum zatvaranja (deaktivacije) objekta

DeactivateFacility
Path: Htz/DeactivateFacility/
Atributi:
ID (guid) - obavezan podatak, ID objekta koji se deaktivira
DocumentID (guid) - obavezan podatak, ID dokumenta temeljem kojeg se deaktivira objekt
TTPayerDeactivationBasisID (guid) - obavezan podatak, temelj deaktivacije, vrijednost iz browse-a TTPayerDeactivationBasisLookup
TypeOfInterestCalculationID (guid) - obavezan podatak, vrsta obračuna kamata nakon deaktivacije, vrijednost iz browse-a TypeOfInterestCalculation
ValidityDate (date) - obavezan podatak, datum od kojeg vrijedi deaktivacija
DecisionNumber (string) - obvezan podatak ako je riječ o komercijalnom objektu, broj dokumenta
DecisionClass (string) - obvezan podatak ako je riječ o komercijalnom objektu, klasa dokumenta
DecisionFileNumber (string) - obvezan podatak ako je riječ o komercijalnom objektu, urudžbeni broj dokumenta

ImportTouristCheckOut
Path: Htz/ImportTouristCheckOut/
Atributi:
ID (guid)
TTPayerID (guid) - ID obveznika na kojeg se odnosi akcija; ako je trenutni korisnik turistička zajednica onda je podatak obavezan inače se ne proslijeđuje; vrijednost iz browse-a TTPayerLookup filtriranog po Pin (OIB obveznika)
Xml (string) - obavezan podatak, primjer datoteke nalazi se u prilogu (TestData/TouristCheckIn.xml), opis sadržaja datototeke:
Svi podaci su obavezni
Dozvoljene vrijednosti šifrarnika korištenih u pozivima metoda dostupne su ovdje
ID - guid, identifikator prijave turista, ako je proslijeđen onda nije potrebno proslijeđivati parametre Facility, DocumentType i DocumentNumber
Facility - šifra objekta u kojem je turist prijavljen
DocumentType - šifra vrste isprave kojom turist potvrđuje identitet
DocumentNumber - broj isprave kojom turist potvrđuje identitet
CheckOutDate - datum odjave turista (format: YYYYMMDD, primjer 20150413)
CheckOutTime - vrijeme odjave turista (format: hh:mm, primjer 09:42)
Validacija podataka:
Upisan datum odjave je manji od datuma boravka od. (item.CheckOutDate < item.StayFrom)
Datum odjave turista ne smije biti veći od današnjeg datuma. (item.CheckOutDate > Today)
Nije dopušten unos datuma odjave koji ne zadovoljava definirana prava. ( x. CheckOutDate <= (Today - parameters.AllowedNumberOfDaysToCheckInCheckOut))

ImportTourists
NAPOMENA: Od 01.06.2017. atribut ID identifikator turista je obvezan, svi pozivi ove metode trebaju imati ID.
Path: Htz/ImportTourists/
Atributi:
Register (bool) - obavezan podatak, potrebno je slati vrijednost true
TTPayerID (guid) - ID obveznika na kojeg se odnosi akcija; ako je trenutni korisnik turistička zajednica onda je podatak obavezan inače se ne proslijeđuje; vrijednost iz browse-a TTPayerLookup filtriranog po Pin (OIB obveznika)
Xml (string) - obavezan podatak, primjer datoteke nalazi se u prilogu (TestData/TouristCheckIn.xml), opis sadržaja datototeke:
Svi podaci su obavezni osim onih koji su označeni kao opcionalni ili je opisan uvjet kad je podatak obavezan
Dozvoljene vrijednosti šifrarnika korištenih u pozivima metoda dostupne su ovdje
ID - guid, identifikator prijave turista, ako se proslijedi onda se može upotrebiti za izmjenu ili odjavu određene prijave turista
Facility - šifra objekta u koji se turist prijavljuje. Šifra objekta je objektu dana od sustava e-Visitor.
StayFrom - datum od kojeg turist boravi u objektu (format: YYYYMMDD, primjer 20150413)
TimeStayFrom - vrijeme od kojeg turist boravi u objektu (format: hh:mm, primjer 09:42)
ForeseenStayUntil - datum do kojeg turist predviđa boraviti u objektu (format: YYYYMMDD, primjer 20150413)
TimeEstimatedStayUntil - vrijeme do kojeg turist predviđa boraviti u objektu (format: hh:mm, primjer 09:42)
DocumentType - šifra vrste isprave kojom turist potvrđuje identitet
DocumentNumber - broj isprave kojom turist potvrđuje identitet
TouristName - ime turista
TouristMiddleName - srednje ime turista (opcionalno)
TouristSurname - prezime turista
Gender - ženski/muški
CountryOfBirth – tro-slovna šifra države (ISO oznaka) rođenja (npr. HRV za Hrvatsku ili DEU za Njemačku)
CityOfBirth – ukoliko je država rođenja Hrvatska, onda ovdje treba staviti naziv grada-naselja rođenja u obliku „grad-naselje“ iz pripremljenog šifrarnika, npr. „Zagreb-Adamovec“. Ukoliko država rođenja nije Hrvatska, onda ovdje treba biti upisan naziv grada iz te države s tim da trenutno sustav prihvaća slobodni unos
DateOfBirth - datum rođenja turista (format: YYYYMMDD, primjer 19760413)
Citizenship – tro-slovna šifra države (ISO oznaka) čije državljanstvo ima turist (npr. HRV za Hrvatsku ili DEU za Njemačku)
CountryOfResidence – tro-slovna šifra države (ISO oznaka) prebivališta (npr. HRV za Hrvatsku ili DEU za Njemačku)
CityOfResidence - ukoliko je država prebivališta Hrvatska, onda ovdje treba staviti naziv grada-naselja prebivališta u obliku „grad-naselje“ iz pripremljenog šifrarnika, npr. „Zagreb-Adamovec“. Ukoliko država prebivališta nije Hrvatska, onda ovdje treba biti upisan naziv grada iz te države s tim da trenutno sustav prihvaća slobodni unos
ResidenceAddress - ulica i broj prebivališta
BorderCrossing - šifra graničnog prijelaza (obavezno ukoliko je turist iz države koja nije članica EU)
PassageDate - datum ulaska u EU (obavezno ukoliko je turist iz države koja nije članica EU)
TTPaymentCategory - šifra kategorije plaćanja boravišne pristojbe
TouristEmail - e-mail turista, opcionalno (podatak se validira, stoga mora biti validna email adresa)
TouristTelephone - kontakt telefon turista, opcionalno (validan format: +385916655333)
ArrivalOrganisation - šifra (MUP) organizacije dolaska, vrijednost CodeMI iz browse-a ArrivalOrganisationLookup
TouristAgency - OIB ili VAT number turističke agencije, ukoliko je organizacija dolaska putem agencije. vrijednost iz browse-a TouristAgencyBrowse. Ukoliko ne postoji tražena agencija možete unijeti novu agenciju u sustav pomoću entity resursa TouristAgency Neobavezan podatak ukoliko ArrivalOrganisation je "Osoban". Ukoliko je "Agencijski" onda je TuristAgency obvezan podatak.
OfferedServiceType - naziv vrste pružene usluge
IsTTFlatRatePaymentVacationHome (bool) - opcionalno; želi plaćati pristojbu paušalno; polje nije obavezno
AccommodationUnitType (string) - podatak nije obavezan, naziv vrste smještajne jedinice, vrijednost iz browse-a AccommodationUnitFacilityType filtriran po FacilityCode
EditOfExistingCheckIn – opcionalni podatak. Ukoliko želite izmijeniti postojeću prijavu zbog greške u unosu onda u ovom polju šaljite vrijednost true. Samo aktivna prijava se može izmijeniti, a ključ za identifikaciju postojeće prijave (ukoliko nije proslijeđen ID parametar) su slijedeći podaci: DocumentType, DocumentNumber, DateOfBirth, CountryResidenceID, TouristName. Prilikom izmjene potrebno je slati sve podatke, a ne samo one koje želite izmjeniti.
Validacija podataka:
Upisan datum boravka do je manji od datuma boravka od. (item.StayFrom > item.ForeseenStayUntil)
Upisano vrijeme odlaska je manje od upisanog vremena dolaska. (item.StayFrom == item.ForeseenStayUntil && item.TimeEstimatedStayUntil <= item.TimeStayFrom)
Potrebno je upisati granični prijelaz, te datum prijelaza. (item.CountryResidence.IsEUMember == false && (item.BorderCrossingHr == null || item.PassageDate == null)
Prekoračen je maksimalan broj dana boravka turista. (item.ForeseenStayUntil - item.StayFrom) > MaximumTouristsDaysOfStay)
Turist je već prijavljen u navedenom objektu. (x.Facility == item.Facility && x.DateOfBirth == item.DateOfBirth && x.DocumentTtype == item.DocumentTtype && x.DocumentNumber == item.DocumentNumber && x.CountryResidence == item.CountryResidence && item. CheckedOutTourist == false && item.TouristCancelled == false)
Nije dopušten unos datuma boravka od koji ne zadovoljava definirana prava. ( x.StayFrom <= (Today - parameters.AllowedNumberOfDaysToCheckInCheckOut))
Paušalno plaćanje dozvoljeno je samo za kuće za odmor do 15.7. u godini. (x => x.IsTTFlatRatePaymentVacationHome == true && (x.Facility.FacilitySubcategory.TTCalculationType.IsVacationHomeCalculation == false || x.StayFrom > new DateTime(DateTime.Today.Year, 7, 15))
Paušalno plaćanje nije dozvoljeno za turiste koji nisu iz europskog gospodarskog pojasa. (item => item.Facility.FacilitySubcategory.TTCalculationType.IsVacationHomeCalculation == true && item.CitizenshipCountry.IsEEAMember == false && item.IsTTFlatRatePaymentVacationHome == true)
Grad rođenja nije zadan. (item => string.IsNullOrEmpty(item.CityOfBirthAbroad) && item.CityOfBirthSettlementHrID == null)
Grad prebivališta nije zadan. (item => string.IsNullOrEmpty(item.CityResidenceAbroad) && item.CityOfResidenceSettlementHrID == null)
StayFrom i TimeStayFrom podatke obveznik ne može naknadno mijenjati. TZ može mijenjati navedene podatke unutar perioda zadanih sistemskim parametrom kojeg određuje HTZ.
TTPaymentCategory mora biti dozvoljen za proslijeđeni objekt (lista dozvoljenih kategorija obračuna boravišne pristojbe moguće je dobiti iz browse-a TTPaymentCategoryLookup2, filtriran po FacitlityID)

SaveCashDiaryPayment
Path: Htz/SaveCashDiaryPayment/
Atributi:
CashDeskID (guid) - obavezan podatak, vrijednost iz browse-a CashDeskLookup
CashDiaryPayment (string) - obavezan podatak, objekt tipa CashDiaryPayment serijaliziran u JSON
FacilityID (guid) - obavezan podatak ako se radi o uplati, vrijednost iz browse-a FacilityBrowse
PayoutDate (datetime) - ako datum nije zadan sustav automatski uzima trenutni datum kao vrijednost

SaveFacility
Path: Htz/SaveFacility/
Atributi:
ID (guid)
AccommodationUnits (string) - obavezan podatak, lista entiteta AccommodationUnit serijalizirana u JSON
AdditionalCategories (string) - lista entiteta FacilityAdditionalCategory serijalizirana u JSON
Codess (string) - dodatne oznake objekta; lista entiteta FacilityFacilityCode serijalizirana u JSON
Facility (string) - obavezan podatak, entitet Facility serijaliziran u JSON
PeriodNote (string) - napomena turističke zajednice vezana za period rada objekta
WorkPeriod (string) - lista entiteta OpenFacilityPeriod serijalizirana u JSON
FacilityYearPaysTTFlatAmount (string) - lista entiteta FacilityYearPaysTTFlatAmount serijalizirana u JSON - obvezan podatak
Validacija:
Prilikom izjmene podataka datum rješenja (DecisionDate) mora biti veći ili jednak od prethodnom.

SaveFacilityCharacteristics
Path: Htz/SaveFacilityCharacteristics/
Atributi:
ID (guid)
CheckIn (datetime)
CheckOut (datetime)
CodeMI (string)
Distances (string) - lista entiteta FacilityDistance serijalizirana u JSON
Email (string)
Fax (string)
Lat (decimal)
Lon (decimal)
Services (string) - lista entiteta FacilityService serijalizirana u JSON
Telephone1 (string)
Telephone2 (string)
TouristAcceptancePeriod (string) - lista entiteta TouristAcceptancePeriod serijalizirana u JSON
Web (string)
AutomaticTouristCheckout (bool)

SaveTTPayer
Path: Htz/SaveTTPayer/
Atributi:
ID (guid) - obavezan podatak
City (string) - obavezan podatak ako država (CountryID) nije Hrvatska
CountryID (guid) - obavezan podatak, vrijednost iz browse-a CountryLookup
FirstName (string) - obavezan podatak ako je obveznik fizička osoba, inače se ne upisuje
IsFRFOwner (bool) - (vlasnik OPG-a) obavezan podatak ako je obveznik fizička osoba, inače se ne upisuje
IsNaturalPerson (bool) - (je fizička osoba) obavezan podatak, true ako je obveznik fizička osoba inače false
IsTradeOwner (bool) - (vlasnik obrta) obavezan podatak ako je obveznik fizička osoba, inače se ne upisuje
LegalPersonTypeID (guid) - obavezan podatak ako je obveznik pravna osoba, inače se ne upisuje, vrijednost iz browse-a LegalPersonTypeLookup
Name (string) - obavezan podatak ako je obveznik pravna osoba, inače se ne upisuje
OpeningBasisID (guid) - obavezan podatak, vrsta dokumenta temelja otvaranja obveznika, vrijednost iz browse-a OpeningBasisLookup
OpeningBasisDocumentID (guid) - obavezan podatak, vrijednost iz entiteta Document (dokument se dodaje pozivom UploadDocument)
Pin (string) - obavezan podatak, OIB obveznika
SettlementHrID (guid) - obavezan podatak ako je država (CountryID) Hrvatska, vrijednost iz browse-a SettlementLookup
StreetNumber (string) - obavezan podatak, ulica i kućni broj
Surname (string) - obavezan podatak ako je obveznik fizička osoba, inače se ne upisuje
ZIPCode (string) - obavezan podatak

SaveTTPayerAdditionalData
Path: Htz/SaveTTPayerAdditionalData/
Atributi:
ContactPerson (string) - obavezan podatak, sadrži serijalizirani JSON objekt entiteta ContactPerson
Documents (string) - sadrži serijalizirani JSON objekt entiteta Document
FRFOwner (string) - obavezan podatak ako je obveznik fizička osoba, sadrži serijalizirani JSON objekt entiteta FRFOwner
IsFRFOwner (bool) - obavezan podatak ako je obveznik fizička osoba
IsTradeOwner (bool) - obavezan podatak ako je obveznik fizička osoba
NoteTB (string) - napomena turističke zajednice koja unosi podatke
TradeOwner (string) - obavezan podatak ako je obveznik fizička osoba, sadrži serijalizirani JSON objekt entiteta TradeOwner
ID parametar pojedinih entiteta koji se prosljeđuju mora biti istovjetan onom koji je proslijeđen u pozivu SaveTTPayer akcije

SaveTuristiZaObracunBoravisnePristojbeTemp
Path: Htz/SaveTuristiZaObracunBoravisnePristojbeTemp/
Atributi:
IDTTCalculationTemp (guid) - obavezan podatak, identifikator za instancu okvirnog obračuna (koristi se prilikom dohvata rezultata obračuna)
TTCalculationTouristTempParam (string) - obavezan podatak, sadrži serijalizirani JSON objekt liste entiteta TTCalculationTouristTemp

UploadDocument
Path: Htz/UploadDocument/
Atributi:
ID (guid)
Content (byte[]) - obavezan podatak, sadržaj datoteke
FileName (string) - obavezan podatak





Entiteti¶
Svi resursi u ovom poglavlju podržavaju metode opisane u poglavlju Entity

AccommodationUnit
Path: Htz/AccommodationUnit/
Atributi:
ID (guid)
CategoryID (guid) - obavezan podatak, vrijednost iz browse-a FacilityCategoryLookup
FacilityID (guid) - obavezan podatak, veza na entitet Facility
NumberOfBeds (int) - obavezan podatak
NumberOfEquivalentUnits (int) - obavezan podatak
NumberOfExtraBeds (int)
Sequence (int) - koristi se za sortiranje podataka za prikaz korisniku
TypeID (guid) - obavezan podatak, vrijednost iz browse-a AccommodationUnitTypePerSubtype (browse se filtrira po atributu FacilitySubcategoryID)

AccommodationUnitCharacteristics
Path: Htz/AccommodationUnitCharacteristics/
Atributi:
ID (guid)
AccommodationUnitID (guid) - obavezan podatak, veza na entitet AccommodationUnit
Name (string) - obavezan podatak
Price (string)
Sequence (int) - obavezan podatak, koristi se za sortiranje podataka za prikaz korisniku
TouristAcceptanceFromFacility (bool)

CashDiaryPayment
Path: Htz/CashDiaryPayment/
Atributi:
ID (guid)
AmountPayments (money) - iznos uplate
PaymentPayoutTypeID (guid) - obavezan podatak, tip uplate/isplate, vrijednost iz browse-a PaymentPayoutTypeLookup
PayoutAmount (money) - iznos isplate
ReasonForPayment (string)
RefeivedFrom (string)
Ovisno o tipu uplate/isplate mora se unijeti određeni iznos (AmountPayments ili PayoutAmount)

ContactPerson
Path: Htz/ContactPerson/
Atributi:
ID (guid)
City (string) - ako je IsUser = false obavezan podatak ako država (CountryID) nije Hrvatska
CountryID (guid) - ako je IsUser = false obavezan podatak, vrijednost iz browse-a CountryLookup
Email (string)
Fax (string)
FirstName (string) - ako je IsUser = false obavezan podatak
InternetPage (string)
IsUser (bool) - obavezan podatak
SettlementHrID (guid) - ako je IsUser = false obavezan podatak ako je država (CountryID) Hrvatska, vrijednost iz browse-a SettlementLookup
StreetNumber (string) - ako je IsUser = false obavezan podatak
Surname (string) - ako je IsUser = false obavezan podatak
Telephone1 (string)
Telephone2 (string)
Telephone3 (string)
ZIPCode (string)

Facility
Path: Htz/Facility/
Atributi:
ID (guid)
Code (string) - obavezan podatak, ovo je autocode atribut (potrebno je unijeti vrijednost '+' da se automatski generira slijedeća vrijednost)
DecisionClass (string) - obvezan podatak ako je riječ o objektu u domaćinstvu
DecisionDate (date) - obavezan podatak
DecisionDocumentID (guid) - obavezan podatak, vrijednost ID-a proslijeđenog u ranije pozvanoj akciji UploadDocument
DecisionFileNumber (string) - obavezan podatak
DecisionNumber (string) - obavezan podatak
DecisionNumberOfEquivalentFacilities (int)
FacilityCategoryID (guid) - vrijednost iz browse-a FacilityCategoryLookup
FacilityLinkToNaturalPersonID (guid) - obavezan podatak ako je obveznik na kojeg ej objekt vezan fizička osoba, vrijednost iz browse-a FacilityLinkToNaturalPersonPerTTPayer
FacilitySubcategoryID (guid) - obavezan podatak, vrijednost iz browse-a
Name (string) - obavezan podatak
Note (string)
SettlementHrID (guid) - obavezan podatak, vrijednost iz browse-a SettlementLookup
SettlementZoneID (guid) - obvezan podatak ako su definirane zone za naselje, vrijednost iz browse-a SettlementZoneLookup (browse se filtrira po atributu SettlementHrID)
StreetNumber (string) - obavezan podatak
TTPayerID (guid) - obavezan podatak, veza na entitet TTPayer
Validacija:
Prilikom izjmene podataka datum rješenja (DecisionDate) mora biti veći ili jednak od prethodnom.

FacilityAdditionalCategory
Path: Htz/FacilityAdditionalCategory/
Atributi:
ID (guid)
FacilityID (guid) - obavezan podatak, veza na entitet Facility
FacilityCategoryID (guid) - obavezan podatak, vrijednost iz browse-a FacilityCategoryLookup

FacilityDistance
Path: Htz/FacilityDistance/
Atributi:
ID (guid)
DistanceID (guid) - obavezan podatak, vrijednost iz browse-a DistanceLookup
DistanceTypeID (guid) - obavezan podatak, vrijednost iz browse-a DistanceTypeLookup
FacilityCharacteristicsID (guid) - obavezan podatak, veza na entitet Facility

FacilityFacilityCode
Path: Htz/FacilityFacilityCode/
Atributi:
ID (guid)
FacilityID (guid) - obavezan podatak, veza na entitet Facility
FacilityCodeID (guid) - obavezan podatak, vrijednost iz browse-a FacilityCodeLookup
Sequence (int) - obavezan podatak, koristi se za sortiranje podataka za prikaz korisniku

FacilityNsoData
Path: Htz/FacilityNsoData/
Atributi:
ID (guid)
Active (bool) - obavezan podatak
FacilityID (guid) - obavezan podatak, vrijednost iz browse-a FacilityBrowse
NumberOfSoldUnits (int) - obavezan podatak, ukupan broj prodanih soba i apartmana za određeni mjesec
NumberWorkingDays (int) - obavezan podatak, broj radnih dana u mjesecu
YearMonth (date) - obavezan podatak, prvi dan u mjesecu za koji vrijedi ovaj podatak

FacilityService
Path: Htz/FacilityService/
Atributi:
ID (guid)
FacilityCharacteristicsID (guid) - obavezan podatak, veza na entitet Facility
HasService (bool) - obavezan podatak
ServiceTypeID (guid) - obavezan podatak, vrijednost iz browse-a ServiceTypeLookup

FacilityYearPaysTTFlatAmount
Path: Htz/FacilityFacilityCode/
Atributi:
ID (guid)
FacilityID (guid) - obavezan podatak, veza na entitet Facility
PaysTTFlatAmount (bool) - obavezan podatak
Year (int) - obavezan podatak, godina na koju se odnosi podatak

FRFOwner
Path: Htz/FRFOwner/
Atributi:
ID (guid)
BasedOnDocumentsID (guid) - obavezan podatak, vrijednost ID-a proslijeđenog u ranije pozvanoj akciji UploadDocument
City (string) - obavezan podatak ako država (CountryID) nije Hrvatska
CountryID (guid) - obavezan podatak, vrijednost iz browse-a CountryLookup
InternetPage (string)
Name (string) - obavezan podatak
SettlementHrID (guid) - obavezan podatak ako je država (CountryID) Hrvatska, vrijednost iz browse-a SettlementLookup
StreetNumber (string) - obavezan podatak
ValidityDateFrom (date) - obavezan podatak
ZIPCode (string) - obavezan podatak
Podaci o vlasniku OPG-a

MITTPayerFiles
Path: Htz/MITTPayerFiles/
Atributi:
ID (guid)
Content (byteJavno.) - obavezan podatak, sadržaj datoteke
FileName (string) - obavezan podatak, naziv datoteke
TTPayerID (guid) - obavezan podatak, veza na entitet Javno.
FileName (string) - obavezan podatak, naziv datoteke
TTPayerID (guid) - obavezan podatak, veza na entitet[]) - obavezan podatak, sadržaj datoteke
FileName (string) - obavezan podatak, naziv datoteke
TTPayerID (guid) - obavezan podatak, veza na entitet [
UploadTime (datetime) - obavezan podatak, vrijeme kreiranja datoteke

OpenFacilityPeriod
Path: Htz/OpenFacilityPeriod/
Atributi:
ID (guid)
DateFrom (date) - obavezan podatak
DateUntil (date) - obavezan podatak
OpenFacilityPeriodInfoID (guid) - obavezan podatak, veza na entitet Facility

TouristAcceptancePeriod
Path: Htz/TouristAcceptancePeriod/
Atributi:
ID (guid)
DateFrom (date) - obavezan podatak
DateUntil (date) - obavezan podatak
FacilityID (guid) - obavezan podatak, veza na entitet Facility

TouristAgency
Path: Htz/TouristAgency/
Atributi:
ID (guid)
Active (bool) - oznaka da li je podatak aktivan u sustavu
Address (string) - adresa sjediišta agencije (ulica i broj)
CountryID (guid) - država sjedišta agencije, vrijednost iz browse-a CountryLookup
IsNaturalPerson (bool) - oznaka da li je agencija registrirana kao fizička ili pravna osoba
Name (string) - obavezan podatak, naziv agencije
Pin (string) - OIB agencije
SettlementAbroad (string) - dio adrese, strani grad (ukoliko je strana agencija) u kojem je sjedište agencije
SettlementHrID (guid)- dio adrese, grad u Hrvatskoj (ukoliko je sjedište agencije u Republici Hrvatskoj) u kojem je sjedište agencije
Vat (string) - strani porezni broj agencije (ukoliko je strana agencija)
Validacija:
obavezan je unos jednog od podataka Pin ili Vat

TradeOwner
Path: Htz/TradeOwner/
Atributi:
ID (guid)
BasedOnDocumentsID (guid) - obavezan podatak, vrijednost ID-a proslijeđenog u ranije pozvanoj akciji UploadDocument
City (string) - obavezan podatak ako država (CountryID) nije Hrvatska
CountryID (guid) - obavezan podatak, vrijednost iz browse-a CountryLookup
InternetPage (string)
Name (string) - obavezan podatak
SettlementHrID (guid) - obavezan podatak ako je država (CountryID) Hrvatska, vrijednost iz browse-a SettlementLookup
StreetNumber (string) - obavezan podatak
ValidityDateFrom (date) - obavezan podatak
ZIPCode (string) - obavezan podatak
Podaci o vlasniku obrta

TTCalculationTouristTemp
Path: Htz/TTCalculationTouristTemp/
Atributi:
ID (guid)
TouristID (guid) - obavezan podatak
CheckOutTime (datetime) - obavezan podatak, vrijeme odjave s kojim će se računati prilikom okvirnog obračuna

Browse¶
Svi resursi u ovom poglavlju podržavaju metode opisane u poglavlju Browse

AccommodationUnitFacilityType
Path: Htz/AccommodationUnitFacilityType/
Atributi:
ID (guid)
FacilityID (guid)
NameCode (string)
FacilityCode (string)
Ovaj pregled je osmišljen tako da se filtrira po atributu FacilityID ili FacilityCode

AccommodationUnitForEdit
Path: Htz/AccommodationUnitForEdit/
Atributi:
ID (guid)
CategoryID (guid)
FacilityID (guid)
FacilityCategoryTypeID (guid)
NumberOfBeds (int) - broj kreveta
NumberOfEquivalentUnits (int) - broj pomoćnih kreveta
NumberOfExtraBeds (int) - broj istovjetnih jedinica u objektu
Sequence (int) - redoslijed kojim se prikazuju smještajne jedinice u sučelju
TypeID (guid) - tip smještajne jedinice, vrijednost iz browse-a AccommodationUnitTypePerSubtype
Ovaj pregled je osmišljen tako da se filtrira po atributu FacilityID

AccommodationUnitTypePerSubtype
Path: Htz/AccommodationUnitTypePerSubtype/
Atributi:
ID (guid)
Active (bool)
FacilitySubcategoryID (guid)
MaximumNumberOfBeds (int)
MaximumNumberOfExtraBeds (int)
MaximumNumberOfSameUnits (int)
Name (string)
Ovaj pregled je osmišljen tako da se filtrira po atributu FacilitySubcategoryID

ArrivalOrganisationLookup
Path: Htz/ArrivalOrganisationLookup/
Atributi:
ID (guid)
Active (bool)
CodeMI (string)
Name (string)
Sequence (int)

CashDeskLookup
Path: Htz/CashDeskLookup/
Atributi:
ID (guid)
Active (bool)
Address (string)
BankAccountID (guid)
CashDeskWithSaldoName (string)
Iban (string)
Name (string)
Settlement (string)
TouristBoardID (guid)

CountryLookup
Path: Htz/CountryLookup/
Atributi:
ID (guid)
Active (bool)
AlternativeName (string)
CodeThreeLetters (string)
CodeTwoLetters (string)
IsEUMember (bool)
IsVisaRequired (bool)
NameCitizenships (string)
NameNational (string)
NameNationalAlternative (string)

DistanceLookup
Path: Htz/DistanceLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)
Sequence (int) - koristi se za sortiranje podataka za prikaz korisniku

DistanceTypeLookup
Path: Htz/DistanceTypeLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)
Sequence (int) - koristi se za sortiranje podataka za prikaz korisniku

FacilityBrowse
Path: Htz/FacilityBrowse/
Atributi:
ID (guid)
AccommodationUnits (string)
Category (string)
Code (string)
Decision (string)
Decision2 (string)
DecisionUploadTime (datetime)
FacilityLinkToNaturalPerson (string)
FacilityType (string)
IsDeactivated (bool)
Name (string)
Note (string)
OpenFacilityPeriod (string)
PaysTTFlatAmount (string)
Settlement (string)
SettlementHrID (guid)
SettlementZone (string)
StreetNumber (string)
TTPayerID (guid)
TTPayerNaturalPerson (bool)
Primjer poziva metode da bi se dobio ID objekta:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/FacilityBrowse/?filters=[{"Property":"Code","Operation":"equal","Value":"123456"}]


FacilityCharacteristicsBrowse
Path: Htz/FacilityCharacteristicsBrowse/
Atributi:
ID (guid)
AutomaticTouristCheckout (bool)
CheckInOut (string)
CodeMI (string)
Distances (string)
Email (string)
Fax (string)
GpsCoordinates (string)
Services (string)
Telephone (string)
TouristAcceptancePeriod (string)
Web (string)

FacilityCategoryLookup
Path: Htz/FacilityCategoryLookup/
Atributi:
ID (guid)
Active (bool)
FacilityCategoryTypeID (guid)
Name (string)

FacilityCodeLookup
Path: Htz/FacilityCodeLookup/
Atributi:
ID (guid)
Active (bool)
FacilitySubcategoryID (guid)
FacilitySubtypeName (string)
FacilityTypenName (string)
Name (string)

FacilityLinkToNaturalPersonPerTTPayer
Path: Htz/FacilityLinkToNaturalPersonPerTTPayer/
Atributi:
ID (guid)
Name (string)
TTPayerID (guid)

FacilitySubcategoryLookup
Path: Htz/FacilitySubcategoryLookup/
Atributi:
ID (guid)
Active (bool)
FacilityTypeID (guid)
FacilityTypenName (string)
HasCodes (bool)
MandatoryDecisionInput (bool)
Name (string)
NecessaryCalculationOfEquivalentUnits (bool)

FacilityTouristCheckInLookup
Path: Htz/FacilityTouristCheckInLookup/
Atributi:
Code (string)
ID (guid)
IsVacationHomeCalculation (bool)
Name (string)
NecessarySettlementRegistration (bool)
SettlementHrID (guid)
TTPayerID (guid)

LegalPersonTypeLookup
Path: Htz/LegalPersonTypeLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)

ListOfTourists
Path: Htz/
Atributi:
ID (guid)
FacilityID (guid)
TTPayerID (guid)
SettlementHrID (guid)
CheckedOutTourist (bool)
SurnameAndName (string)
DateTimeOfArrival (datetime)
DateTimeOfDeparture (datetime)
Citizenship (string)
FacilityName (string)
TouristCheckedOutString (string)
Pregled vraća sve prijavljene i odjavljene turiste. Pregled ne vraća poništene prijave.
Primjer poziva metode koji vraća turiste koji su boravili od 1.1.2017:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/ListOfTourists/?psize=20&page=1&filters=[{"Property":"StayFrom","Operation":"greaterequal","Value":"\/Date(1483225200000+0100)\/"}]&sort=DateTimeOfArrival%20asc


ListOfTouristsExtended
Path: Htz/
Atributi:
ID (guid)
Address (string)
ApplicationNumber (string)
CardNumber (string)
CheckedOutTourist (bool)
Citizenship (string)
DatePlaceOfBirth (string)
DatePlaceOfEntryInRC (string)
DateTimeOfArrival (datetime)
DateTimeOfDeparture (datetime)
FacilityID (guid)
FacilityName (string)
ForeseenStayUntil (date)
Gender (string)
Note (string)
PermitOfStayDate (date)
SettlementHrID (guid)
StayFrom (date)
SurnameAndName (string)
TouristCheckedOutString (string)
TravelDocumentTypeNumber (string)
TTPayerID (guid)
Pregled vraća sve prijavljene i odjavljene turiste. Pregled ne vraća poništene prijave.
Primjer poziva metode koji vraća turiste koji su boravili od 1.1.2017:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/ListOfTouristsExtended/?psize=20&page=1&filters=[{"Property":"StayFrom","Operation":"greaterequal","Value":"\/Date(1483225200000+0100)\/"}]&sort=StayFrom%20asc




ManualApprovalDebitBrowse
Path: Htz/ManualApprovalDebitBrowse/
Atributi:
ID (guid)
BoolCalculation (bool) - izvor financijskog podatka je obračun boravišne pristojbe
BoolCashDesk (bool) - izvor financijskog podatka je blagajna
BoolFinalReport (bool) - izvor financijskog podatka je izvod
BoolManualApprovalDebit (bool) - izvor financijskog podatka je ručno odobrenje/zaduženje
Date (date) - datum financijskog podatka
Debit (money) - iznos dugovanja
DocumentID (guid)
FacilityID (guid) - identifikacija objekta za koji vrijedi financijski podatak
Note (string) - opis/napomena
Payment (money) - iznos uplate

OpeningBasisLookup
Path: Htz/OpeningBasisLookup/
Atributi:
ID (guid)
Active (bool)
ForNaturalPerson (bool)
Name (string)

PaymentFlatRateSlipSample
Path: Htz/PaymentFlatRateSlipSample/
Atributi:
ID (guid)
Amount1 (money)
Amount2 (money)
Amount3 (money)
AmountString1 (string)
AmountString2 (string)
AmountString3 (string)
Barcode1 (string)
Barcode2 (string)
Barcode3 (string)
CityZIPCode1 (string)
CityZIPCode2 (string)
CityZIPCode3 (string)
Cost1 (string)
Cost2 (string)
Cost3 (string)
Country1 (string)
Country2 (string)
Country3 (string)
Currency1 (string)
Currency2 (string)
Currency3 (string)
ExecutionDate1 (string)
ExecutionDate2 (string)
ExecutionDate3 (string)
Iban1 (string)
Iban2 (string)
Iban3 (string)
IdString (string)
Model1 (string)
Model2 (string)
Model3 (string)
NameSurname (string)
NameSurname1 (string)
NameSurname2 (string)
NameSurname3 (string)
PaymentDescription1 (string)
PaymentDescription2 (string)
PaymentDescription3 (string)
Receiver1 (string)
Receiver2 (string)
Receiver3 (string)
RefNo1 (string)
RefNo2 (string)
RefNo3 (string)
StreetNumber1 (string)
StreetNumber2 (string)
StreetNumber3 (string)
Kolone xx1, xx2 i xx3 odnose se na prvu, drugu, odnosno treću uplatnicu. Ukoliko su kolone xx2 i/ili xx3 null, to znači da za dotični objekt postoji samo jedna uplatnica.

PaymentPayoutTypeLookup
Path: Htz/PaymentPayoutTypeLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)
Payment (bool)
PaymentCancellation (bool)
Payout (bool)
PayoutCancellation (bool)

ServiceTypeLookup
Path: Htz/ServiceTypeLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)
Sequence (int) - koristi se za sortiranje podataka za prikaz korisniku

SettlementLookup
Path: Htz/SettlementLookup/
Atributi:
ID (guid)
Active (bool)
CityMunicipalityHrID (guid)
HasZones (bool)
Name (string)
ZIPCode (string)

SettlementZoneLookup
Path: Htz/SettlementZoneLookup/
Atributi:
ID (guid)
Active (bool)
BasisAmount (money)
Name (string)
Settlement (string)
SettlementHrID (guid)
ZoneID (guid)
Ovaj pregled je osmišljen tako da se filtrira po atributu SettlementHrID.

TouristAgencyBrowse
Path: Htz/TouristAgencyBrowse/
Atributi:
ID (guid)
Active (bool)
Address (string)
Country (string)
IsNaturalPerson (bool)
Name (string)
PinOrVat (string)
Settlement (string)
Ovaj pregled je namijenjen pronalasku turističke agencije po OIB-u ili VAT broju (podatak PinOrVat)
primjer poziva metode:
https://www.evisitor.hr/eVisitorRhetos_API/Rest/Htz/TouristAgencyBrowse/?filters=[{"Property":"Active","Operation":"equal","Value":"true"},{"Property":"PinOrVat","Operation":"equal","Value":"123456789"}]


TouristCheckOut
Path: Htz/TouristCheckOut/
Atributi:
ID (guid)
CheckInDate (date)
DocumentNumber (string)
DocumentTtypeID (guid)
FacilityID (guid)
FacilityName (string)
ForeseenDeparture (date)
RecordedOvernightStays (int)
SettlementHrID (guid)
Tourist (string)
TTPayerID (guid)
TTPaymentCategory (string)
Pregled vraća sve aktivne prijave, odnosno sve prijave koju se spremne za odjavu.

TTCalculationItemSourceByTourist
Path: Htz/TTCalculationItemSourceByTourist/
Atributi:
ID (guid)
Amount (money)
AmountString (string)
CheckInDate (datetime)
CheckOutDate (datetime)
DateOfBirth (date)
Facility (string)
IDTTCalculationTemp (guid)
Note (string)
Tourist (string)
TTPaymentCategory (string)

TTCalculationItemSourceTempBrowse
Path: Htz/TTCalculationItemSourceTempBrowse/
Atributi:
ID (guid)
Amount (money)
IDTTCalculationTemp (guid)
PeriodFrom (date)
PeriodUntil (date)
TouristID (guid)

TTCalculationItemSourceByFacility
Path: Htz/TTCalculationItemSourceByFacility/
Atributi:
ID (guid)
Amount (money)
AmountString (string)
Debt (money)
DebtString (string)
IDTTCalculationTemp (guid)
Name (string)

TTPayerDeactivationBasisLookup
Path: Htz/TTPayerDeactivationBasisLookup/
Atributi:
ID (guid)
Active (bool)
Name (string)

TTPayerFinancialRecord
Path: Htz/TTPayerFinancialRecord/
Atributi:
ID (guid)
Date (DateTime)
Payment (decimal)
Reason (string)
TTPayerID (guid)
FacilityID (guid)
BoolCalculation (bool)
BoolManualApprovalDebit (bool)
BoolCashDesk (bool)
BoolFinalReport (bool)

TTPayerLookup
Path: Htz/TTPayerLookup/
Atributi:
ID (guid)
Name (string)
Pin (string)
RightToTTPayerPrincipalID (guid)

TTPayerUnion
Path: Htz/TTPayerUnion/
Atributi:
ID (guid)
Address (string)
City (string)
CountryID (guid)
DefaultConnectionToNaturalPersonID (guid)
Document (string)
FirstName (string)
IsDeactivated (bool)
IsFRFOwner (bool)
IsNaturalPerson (bool)
IsOwnerTradeFRF (bool)
IsTradeOwner (bool)
LatestChange (datetime)
LegalPersonTypeID (guid)
LegalPersonTypeName (string)
Name (string)
OpeningBasisID (guid)
OpeningBasisDocumentID (guid)
Pin (string)
SettlementHrID (guid)
StreetNumber (string)
Surname (string)
UserType (string)
ZIPCode (string)

TTPaymentCategoryLookup2
Path: Htz/TTPaymentCategoryLookup2/
Atributi:
ID (guid)
FacilityID (guid)
Active (bool)
Code (string)
CodeNames (string)
Name (string)
Pregled je zamišljen da se filtrira po FacilityID i Active=true, vraća dozvoljene kategorije plaćanja za određeni objekt.

TypeOfInterestCalculation
Path: Htz/TypeOfInterestCalculation/
Atributi:
ID (guid)
Name (string)

!!! NOVO !!! Upute za dodijelu pristupnih podataka ¶
Dodatna objašnjenja i upute za obveznike i turističke zajednice u vezi dodijelu pristupnih podataka nalaze se ovdje: Testna okolina - pristupni podaci.docx

!!! NOVO !!! ¶
Upute za provjeru API integracije sa sustavom eVisitor Dodatna objašnjenja i upute za provjeru integracije se nalaze ovdje: Upute za provjeru API integracije sa sustavom eVisitor.pdf

!!! NOVO 2022 !!! ¶
Krivo implementirani API pozivi Trenutačno eVisitor ima veće sigurnosne provjere nego prijašnje verzije sustava i neće više prihvatiti krivo implementirane API pozive. Molimo da API vendori provjere upute na postojećim Wiki stranicama i naprave reviziju svojih poziva prema eVisitoru te jesu li uredno implementirani prema uputi.

Najčešće greške koje se javljaju API vendorima:

1. Q: API je vratio grešku: „The requested URL was rejected. Please consult with your administrator. Your support ID is: 11000…“
A: Spojili ste više cookie-a i jedan, ali ste između njih stavili umjesto „;“ stavili „ “ (ispravljeni primjer php skripte je u prilogu API dokumentacije)
2. Q: Želim zatražiti pomoć od eVisitor podrške.
A: Prije kontaktiranja podrške, molimo vas da napravite ručno poziv na API korištenjem cURL, Postman ili sl. alata te upitu priložiti kompletan poziv i odgovor od alata cURL ili Postman Console Log, osim korisničkog password-a kojeg treba obrisati. Ukoliko zahtjev normalno prođe, molim provjerite da je sve uredu s vaše strane.
3. Q: Da nakon uspješnog logiranja na API, što dalje?
A: Prilikom pozivanja narednih metoda treba obavezno proslijediti sve zaprimljene cookie koje ste inicijalno dobili
4. Q: Pokušavam napraviti import turista ali javljaju mi se greške?
A: API funkcionalnost ImportTourist je ista opcija koja se u sučelju zove „Prijava putem datoteke“.
Ona koristi interni popis neprijavljenih turista (istu onu koja je vidljiva u Turisti / Prijava turista).
Uz to da se nakon zaprimanja XML-a, automatski pozove opcija „Prijavi“ (ista koja je dostupna i kroz sučelje).
Opcija „Prijavi“ oduvijek radi tako da pokuša prijaviti sve turiste iz tog popisa.
Provjerite jesu li svi zapisi ispravni (jer ako je jedan neispravan import neće proći), te provjerite da ne prijavljujete duplo turiste te jesu li istekli rokovi za prijavu.


Ukoliko ste potvrdili da nemate krivo implementiran API poziv i rade sve uredno prema napisanim točkama, a zbog nekog razloga imate i dalje grešku molimo da nam proslijede sljedeće informacije:

Točno vrijeme upita (u sekundu)
Username korisnika
Metodu koja je pozvana
Parametri metode, uključujući i sadržaj (body)
Response status



Povezane stranice¶
WEB API - Novosti
Obveznici - Početni ekran
Obveznici - Prijava turista
Turistička zajednica - Prijava turista
