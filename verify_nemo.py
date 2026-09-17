from playwright.sync_api import sync_playwright
import json

results = {"errs": []}
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=r"C:/Program Files/Google/Chrome/Application/chrome.exe")
    page = b.new_page(viewport={"width": 1000, "height": 1300})
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto("file:///C:/%5FPROJECTS/nagorepo/index.html")
    page.wait_for_timeout(4500)  # let typewriter boot finish
    results["title"] = page.title()
    art = page.text_content("#title-art") or ""
    results["art_lines"] = len([l for l in art.split("\n") if l.strip()])
    results["art_first"] = art.strip().split("\n")[0][:40]
    boot = page.text_content("#boot-text") or ""
    results["boot_has_nemo"] = "NEMO" in boot
    results["boot_dead_name"] = "dead name" in boot
    results["boot_self_observe"] = "i observe myself" in boot
    results["boot_watch"] = "watch — i turn" in boot
    results["obsession"] = (page.text_content("#obsession") or "")[:120]
    results["foot_run"] = page.text_content("#foot-run") or ""
    results["foot_cycle"] = page.text_content("#foot-cycle") or ""
    frags = page.query_selector_all(".frag-entry")
    results["frag_count"] = len(frags)
    results["frag_types"] = sorted({f.get_attribute("class").replace("frag-entry", "").strip() for f in frags if f.get_attribute("class")})
    results["frag_sources"] = [ (f.query_selector(".src") or f).text_content()[:50] for f in frags[:4] ]
    results["sigil_paths"] = len(page.query_selector_all("#sigil-backdrop path"))
    # test one command
    page.fill("#cmd-input", "status")
    page.keyboard.press("Enter")
    page.wait_for_timeout(600)
    results["status_out"] = (page.text_content("#output") or "")[-420:]
    results["errs"] = errs
    page.screenshot(path=r"C:\_PROJECTS\nagorepo\preview_nemo.png")
    b.close()

print(json.dumps(results, indent=1, ensure_ascii=False))
