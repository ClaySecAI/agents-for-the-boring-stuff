"""Create a fake Downloads folder whose files belong to eight projects, plus the answer key.

    python3 make_project_mess.py [target_dir] [--blind]   (default: ./practice-projects/downloads)

--blind replaces the text of every other file with "[scanned page: no text layer]", the way a
scanned PDF looks when nothing can read it. Names, download sources and dates are untouched, so
this mode shows how much the other signals are worth when the contents say nothing.

--hold-out PROJECT leaves that project off projects.json. Its files then belong to no listed
project, and the answer key says Unsorted. It shows what the model does with files that nothing
on your list covers: file them under the nearest project, or leave them unsorted.

--statements adds three account histories that share one account number but say little about
what the account is for, to test linking files by a shared identifier.

--second-batch adds 24 files that "arrive later": from the same websites, with the same kinds of
number, and often with almost no content. It is the test bed for rules learned from corrections.

Writes three things:

  <target_dir>/            59 small files named the way real downloads are named
  <target_dir>/../projects.json   the project list you would normally write yourself
  <target_dir>/../truth.json      which project each file really belongs to (and which
                                  other project it also serves). The agent never sees this.
                                  score.py compares the agent's answers against it.

The fixture is hard on purpose:

  * every document is addressed to the same fake person at the same fake address, so
    names and addresses do not separate the projects
  * a few files have generic names and almost no content ("Order confirmed. Thank you.").
    Only where the file was downloaded from, and when, can place them
  * three files are junk that belongs to no project
  * two documents serve two projects (a conference expense report is also tax paperwork)

On macOS it records a fake download source for each file, the way a browser does
(the com.apple.metadata:kMDItemWhereFroms attribute), using reserved .example domains.
Everything here is invented.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import plistlib
import subprocess
import sys
from pathlib import Path

PERSON, ADDRESS = "Jordan Lee", "42 Elm Street"

# (name, description, download domain, first date)
PROJECTS = [
    ("Kitchen remodel", "Renovating the kitchen at home: contractor quotes, permits, cabinets, tile, inspections.",
     "maplestone-reno.example", "2026-02-03"),
    ("Car purchase", "Buying a new car: dealer paperwork, financing, insurance, registration, trade-in.",
     "sunrisemotors.example", "2026-03-10"),
    ("Conference trip", "A three-day work conference: flights, hotel, registration, agenda, expenses.",
     "summit2026.example", "2026-03-02"),
    ("Insurance claim", "A hail damage claim on the roof: claim paperwork, adjuster report, roofer estimate, payment.",
     "stormshield-ins.example", "2026-04-02"),
    ("Job search", "Looking for and landing a new job: resumes, cover letters, interviews, the offer.",
     "jobboard.example", "2026-05-04"),
    ("Tax prep", "Preparing the 2025 tax return: income forms, receipts, payment vouchers.",
     "taxhelper.example", "2026-02-20"),
    ("Marathon training", "Training for and running a marathon: plans, registration, gear, workout logs.",
     "runclub.example", "2026-05-02"),
    ("Software", "Installers, updates and programs. Not part of any other project.",
     "vendor-downloads.example", "2026-01-15"),
]

# project -> list of (file name, text, also-projects, has download source)
FILES: dict[str, list[tuple[str, str, list[str], bool]]] = {
    "Kitchen remodel": [
        ("maplestone_quote_v2.pdf", f"QUOTE #2231\nMaple & Stone Renovations\nPrepared for: {PERSON}, {ADDRESS}\nScope: demolition, new cabinets, quartz countertop, tile backsplash\nTotal: $28,400. Valid for 30 days.", [], True),
        ("permit_application.pdf", f"CITY BUILDING PERMIT APPLICATION\nProperty: {ADDRESS}. Owner: {PERSON}\nWork: interior kitchen remodel, no structural changes\nFee: $240", [], True),
        ("cabinet_order_confirmation.pdf", f"ORDER CONFIRMATION\nShaker cabinets, 14 units, white\nDelivery to {ADDRESS} in 6 weeks\nOrder total: $6,150", [], True),
        ("tile_invoice_0412.pdf", f"INVOICE\nSubway tile 3x6, 85 sq ft, grout, spacers\nBill to: {PERSON}. Total: $612.40", [], True),
        ("inspection_report.pdf", f"FINAL INSPECTION REPORT\nElectrical: pass. Plumbing: pass. Cabinets and counters installed.\nAddress: {ADDRESS}", [], False),
        ("scan_0042.pdf", "Measurements:\nIsland 4 ft x 7 ft\nUpper cabinets 30 in\nCountertop overhang 1.5 in\n(handwritten notes, scanned)", [], False),
        ("order-88231.pdf", "Order #88231 confirmed. Thank you for your purchase. Questions? Contact support.", [], True),
    ],
    "Car purchase": [
        ("buyers_order.pdf", f"BUYER'S ORDER\nSunrise Motors\nCustomer: {PERSON}, {ADDRESS}\nVehicle: 2024 sedan, VIN ending 4471\nPrice: $31,900. Sales tax: $2,073", ["Tax prep"], True),
        ("loan_preapproval.pdf", f"AUTO LOAN PRE-APPROVAL\nApplicant: {PERSON}\nAmount: up to $30,000 at 5.9% for 60 months", [], True),
        ("insurance_binder.pdf", f"AUTO INSURANCE BINDER\nInsured: {PERSON}\nVehicle: 2024 sedan\nEffective on delivery date. Premium: $118/month", [], True),
        ("registration_form.pdf", f"VEHICLE REGISTRATION APPLICATION\nOwner: {PERSON}, {ADDRESS}\nNew title, plate transfer requested", [], False),
        ("tradein_appraisal.pdf", "TRADE-IN APPRAISAL\n2016 hatchback, 88,000 miles\nAppraised value: $6,200", [], True),
        ("warranty_brochure.pdf", "EXTENDED WARRANTY OPTIONS\nPowertrain 5 years / 60,000 miles\nPlatinum coverage 7 years", [], True),
        ("document(3).pdf", "Thank you. Your documents have been received. We will contact you within 2 business days.", [], True),
    ],
    "Conference trip": [
        ("itinerary_AB1234.pdf", f"FLIGHT ITINERARY\nPassenger: {PERSON}\nOutbound: Mar 9, 7:40 AM  Return: Mar 12, 5:15 PM\nConfirmation: AB1234", [], True),
        ("hotel_confirmation.pdf", f"HOTEL RESERVATION\nHarbor View Hotel, 3 nights, check-in Mar 9\nGuest: {PERSON}. Rate: $189/night", [], True),
        ("registration_receipt.pdf", f"SUMMIT 2026 REGISTRATION RECEIPT\nAttendee: {PERSON}\nFull conference pass: $895. Paid.", [], True),
        ("agenda.pdf", "SUMMIT 2026 AGENDA\nDay 1: keynote, workshops\nDay 2: sessions on data tools\nDay 3: closing panel", [], True),
        ("expense_report_march.csv", "date,item,amount\n2026-03-09,airfare,412.00\n2026-03-10,hotel,567.00\n2026-03-11,meals,96.50", ["Tax prep"], False),
        ("receipt_0310.jpg", "[photo of a taxi receipt] Yellow Cab. Airport to hotel. Fare $38.00", [], False),
        ("IMG_5521.jpg", "[photo] a conference hall with a stage and a large screen", [], True),
    ],
    "Insurance claim": [
        ("claim_confirmation.pdf", f"CLAIM CONFIRMATION\nStormShield Insurance. Claim #HC-77120\nInsured: {PERSON}, {ADDRESS}\nLoss: hail damage to roof, reported Apr 2", [], True),
        ("adjuster_report.pdf", "ADJUSTER REPORT\nClaim #HC-77120. Inspection of roof shingles and gutters.\nEstimated damage: $11,300. Deductible: $1,000", [], True),
        ("roofer_estimate.pdf", "ROOF REPLACEMENT ESTIMATE\nSummit Roofing. 28 squares, architectural shingles\nTotal: $12,050", [], False),
        ("hail_photo_01.jpg", "[photo] dented gutter and cracked shingles after the storm", [], False),
        ("claim_letter.docx", "Letter to StormShield: I am writing to follow up on claim HC-77120 and request an inspection date.", [], False),
        ("payment_letter.pdf", "SETTLEMENT PAYMENT NOTICE\nClaim #HC-77120. Payment issued: $10,300 (net of deductible)", [], True),
        ("scan_0108.pdf", "Page 2 of 3. Continued on next page. Signature: ____", [], True),
    ],
    "Job search": [
        ("resume_2026.docx", f"{PERSON.upper()}\nSoftware developer, 8 years experience\nSkills: Python, SQL, cloud tooling\nEmployment: Acme Data (2021-2026)", [], False),
        ("resume_v3_final.docx", f"{PERSON.upper()}\nSummary: backend engineer focused on data pipelines\nEmployment history follows.", [], False),
        ("cover_letter_bluepeak.docx", "Dear hiring manager at BluePeak Systems, I am applying for the senior developer role advertised on your site.", [], False),
        ("offer_letter.pdf", f"OFFER OF EMPLOYMENT\nBluePeak Systems offers {PERSON} the role of Senior Developer\nBase salary: $148,000. Start date: June 1", [], True),
        ("references.docx", "References\n1. Sam Rivera, former manager\n2. Priya Nair, colleague", [], False),
        ("interview_schedule.pdf", "INTERVIEW SCHEDULE\nRound 1: recruiter call. Round 2: technical interview. Round 3: team panel", [], True),
        ("linkedin_export.csv", "company,title,start\nAcme Data,Developer,2021-03", [], True),
    ],
    "Tax prep": [
        ("w2_2025.pdf", f"FORM W-2 WAGE AND TAX STATEMENT 2025\nEmployee: {PERSON}\nWages: $132,400. Federal tax withheld: $21,800", [], True),
        ("1099_int_bank.pdf", f"FORM 1099-INT 2025\nRecipient: {PERSON}. Interest income: $412.18", [], True),
        ("charity_receipt.pdf", f"DONATION RECEIPT\nHarvest Food Bank. Donor: {PERSON}. Amount: $250. Tax year 2025", [], False),
        ("taxhelper_confirmation.pdf", "TAXHELPER FILING CONFIRMATION\nReturn for tax year 2025 accepted\nFederal refund expected: $1,940", [], True),
        ("estimated_payment_voucher.pdf", f"FORM 1040-ES PAYMENT VOUCHER\nTaxpayer: {PERSON}\nPayment due: Apr 15. Amount: $1,200", [], True),
        ("property_tax_statement.pdf", f"PROPERTY TAX STATEMENT\n{ADDRESS}. Owner: {PERSON}\nAnnual amount: $4,380", [], False),
        ("docs-2025.zip", "[zip archive of scanned receipts for tax year 2025]", [], True),
    ],
    "Marathon training": [
        ("training_plan_16wk.pdf", "16-WEEK MARATHON TRAINING PLAN\nWeek 1: 3 easy runs, long run 8 miles\nPeak week: long run 20 miles", [], True),
        ("race_registration.pdf", f"CITY MARATHON REGISTRATION\nRunner: {PERSON}. Race date: Oct 18\nEntry fee: $140", [], True),
        ("shoe_receipt.pdf", "RUNNING SHOE STORE RECEIPT\nTrail and road shoes, 2 pairs, $289.98", [], False),
        ("workout_log.csv", "date,miles,pace\n2026-05-02,6.2,8:45\n2026-05-04,3.1,8:30\n2026-05-09,12.0,9:05", [], True),
        ("nutrition_plan.pdf", "RACE-WEEK NUTRITION\nCarb loading 3 days before. Breakfast: oatmeal and banana.", [], True),
        ("route_map.gpx", "<gpx><trk><name>Riverside long run</name><trkseg></trkseg></trk></gpx>", [], False),
        ("export_0612.csv", "timestamp,heart_rate\n06:01,128\n06:02,131\n06:03,133", [], True),
    ],
    "Software": [
        ("Zoom.dmg", "[pretend installer] video meeting app", [], True),
        ("python-3.12.2-macos.pkg", "[pretend installer] Python installer package", [], True),
        ("editor-update.zip", "[pretend archive] code editor update", [], True),
        ("printer-driver-installer.pkg", "[pretend installer] printer driver", [], True),
        ("browser-update.dmg", "[pretend installer] web browser update", [], True),
        ("vpn-client.dmg", "[pretend installer] VPN client", [], True),
        ("pdf-reader-setup.dmg", "[pretend installer] PDF reader", [], True),
    ],
}

UNSORTED = [
    ("untitled.txt", "asdf test test"),
    ("notes.txt", "call back about the thing, tuesday?"),
    ("random.bin", "[pretend binary] unknown data"),
]


# --second-batch: files that arrive later, from the same websites and with the same kinds of numbers
# as the first batch, so that rules learned from your corrections about the first batch have something
# to catch. Several are as bland as the first batch's worst ("Thank you. Your documents have been
# received."), which only a website or a number can place.
SECOND_BATCH: dict[str, list[tuple[str, str, list[str], bool]]] = {
    "Kitchen remodel": [
        ("order-88232.pdf", "Order #88232 confirmed. Thank you for your purchase.", [], True),
        ("scan_0201.pdf", "Page 1 of 2. Continued on next page.", [], True),
        ("change_order_2.pdf", "Change order. Reference: MS-2231-02. Please sign and return.", [], True),
    ],
    "Car purchase": [
        ("document(4).pdf", "Thank you. Your documents have been received. We will contact you shortly.", [], True),
        ("scan_0202.pdf", "Page 2 of 3. Signature: ____", [], True),
        ("service_plan.pdf", "Confirmation: thank you for choosing a service plan.", [], True),
    ],
    "Conference trip": [
        ("agenda_day2.pdf", "Day 2 sessions. Room changes are posted at the registration desk.", [], True),
        ("confirmation_e.pdf", "Confirmation received. See you at the event.", [], True),
        ("shuttle_times.pdf", "Shuttle departs every 20 minutes from the main entrance.", [], True),
    ],
    "Insurance claim": [
        ("scan_0109.pdf", "Page 3 of 3. Signature page.", [], True),
        ("claim_followup.pdf", "Re: claim #HC-77120. We received your message and will reply soon.", [], True),
        ("payment_receipt.pdf", "Payment received. Thank you.", [], True),
    ],
    "Job search": [
        ("application_confirmation.pdf", "Your application has been received. Thank you.", [], True),
        ("interview_prep.pdf", "Tips for your upcoming conversation.", [], True),
        ("scan_0301.pdf", "Page 1 of 1.", [], True),
    ],
    "Tax prep": [
        ("document(5).pdf", "Thank you. Your documents have been received. We will contact you shortly.", [], True),
        ("filing_status.pdf", "Your filing status has been updated. Thank you.", [], True),
        ("scan_0401.pdf", "Page 1 of 4.", [], True),
    ],
    "Marathon training": [
        ("export_0613.csv", "timestamp,heart_rate\n06:01,120\n06:02,124\n06:03,127", [], True),
        ("pacing_chart.pdf", "Target splits by mile.", [], True),
        ("scan_0501.pdf", "Page 1 of 1.", [], True),
    ],
    "Software": [
        ("app-installer.dmg", "[pretend installer] new application", [], True),
        ("helper-update.pkg", "[pretend installer] helper tool update", [], True),
        ("driver-pack.zip", "[pretend archive] driver pack", [], True),
    ],
}


def set_download_source(path: Path, url: str) -> None:
    """Record where a file came from, the way a browser does. macOS only."""
    blob = plistlib.dumps([url, ""], fmt=plistlib.FMT_BINARY).hex()
    subprocess.run(["xattr", "-wx", "com.apple.metadata:kMDItemWhereFroms", blob, str(path)],
                   check=True, capture_output=True)


# --statements: three monthly account histories that share one account number. Only the first
# says what the account is for. The other two are tables of payments, so a model reading them
# one at a time has nothing to go on. All three belong to "Car purchase".
STATEMENTS = [
    ("account_history.pdf", f"ACCOUNT HISTORY\nSunrise Motors Financial\nAccount number: 8841-2290-17\nBorrower: {PERSON}\nPayment received 02/01  $551.20\nPayment received 03/01  $551.20\nInterest paid year to date: $214.08", [], False),
    ("account_history (1).pdf", "ACCOUNT HISTORY\nAccount number: 8841-2290-17\nDate | Description | Amount\n04/01 | Payment | 551.20\n05/01 | Payment | 551.20", [], False),
    ("account_history (2).pdf", "ACCOUNT HISTORY\nAccount number: 8841-2290-17\nDate | Description | Amount\n06/01 | Payment | 551.20\n07/01 | Payment | 551.20", [], False),
]


def main() -> None:
    ap = argparse.ArgumentParser(usage=__doc__)
    ap.add_argument("target", nargs="?", default="practice-projects/downloads")
    ap.add_argument("--blind", action="store_true",
                    help="every other document has no readable text, like a scan")
    ap.add_argument("--statements", action="store_true",
                    help="add three account histories that share one account number")
    ap.add_argument("--second-batch", action="store_true",
                    help="add files that arrive later from the same websites, for testing learned rules")
    ap.add_argument("--hold-out", metavar="PROJECT",
                    help="leave this project off the project list; its files truly belong to no listed project")
    opts = ap.parse_args()
    blind, target = opts.blind, Path(opts.target)
    held = opts.hold_out
    if held and held not in FILES:
        sys.exit(f"Unknown project {held!r}. Choose one of: {', '.join(FILES)}")
    all_files = {project: list(files) for project, files in FILES.items()}
    if opts.statements:
        all_files["Car purchase"] += STATEMENTS
    if opts.second_batch:
        for project, extra in SECOND_BATCH.items():
            all_files[project] += extra
    if target.exists() and any(target.iterdir()):
        sys.exit(f"{target} already exists and is not empty. Delete it or pick another path.")
    target.mkdir(parents=True, exist_ok=True)
    domains = {name: domain for name, _desc, domain, _day in PROJECTS}
    starts = {name: datetime.date.fromisoformat(day) for name, _desc, _domain, day in PROJECTS}
    can_tag_source = sys.platform == "darwin"

    truth = {}
    for project, files in all_files.items():
        for index, (name, text, also, has_source) in enumerate(files):
            path = target / name
            if blind and index % 2 == 1:
                # A unique page number keeps the blanked files from being byte-identical, which
                # would make them look like duplicates of each other.
                text = f"[scanned page: no text layer, scan {len(truth) + 1:03d}]"
            path.write_text(text)
            day = starts[project] + datetime.timedelta(days=index * 2)
            stamp = datetime.datetime.combine(day, datetime.time(10, 0)).timestamp()
            os.utime(path, (stamp, stamp))
            if has_source and can_tag_source:
                set_download_source(path, f"https://{domains[project]}/files/{name}")
            # A held-out project is not on the list, so its files truly belong to none of them.
            truth[name] = {"primary": "Unsorted" if project == held else project,
                           "also": [a for a in also if a != held]}
    for name, text in UNSORTED:
        path = target / name
        path.write_text(text)
        truth[name] = {"primary": "Unsorted", "also": []}

    root = target.resolve().parent
    (root / "projects.json").write_text(json.dumps(
        [{"name": n, "description": d} for n, d, _dom, _day in PROJECTS if n != held], indent=2))
    (root / "truth.json").write_text(json.dumps(truth, indent=2))
    note = "" if can_tag_source else " (not macOS: download sources were not recorded)"
    print(f"Created {len(truth)} files in {target}, plus projects.json and truth.json beside it{note}.")


if __name__ == "__main__":
    main()
