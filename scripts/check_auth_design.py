import os
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
(ROOT / 'test-artifacts').mkdir(exist_ok=True)
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / '.playwright'))
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width':1536,'height':1024})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    for route in ['login','register']:
        page.goto(f'http://127.0.0.1:8011/accounts/{route}/')
        page.wait_for_load_state('networkidle')
        page.screenshot(path=str(ROOT / 'test-artifacts' / f'{route}-design.png'), full_page=True)
        assert page.locator('.auth-card').is_visible()
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(ROOT / 'test-artifacts' / f'{route}-mobile.png'), full_page=True)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.set_viewport_size({'width':1536,'height':1024})
    page.goto('http://127.0.0.1:8011/accounts/login/')
    page.locator('[name="username"]').fill(os.environ.get('SMOKE_LOGIN', 'demo@example.com'))
    page.locator('[name="password"]').fill(os.environ['SMOKE_PASSWORD'])
    page.locator('[data-password]').click()
    expect(page.locator('[name="password"]')).to_have_attribute('type','text')
    page.locator('[data-password]').click()
    page.locator('.auth-submit').click()
    page.wait_for_url('http://127.0.0.1:8011/')
    page.wait_for_load_state('networkidle')
    expect(page.locator('#stats .stat')).to_have_count(4)
    expect(page.locator('.top-actions form')).to_have_count(0)
    expect(page.locator('.top-actions a')).to_have_count(0)
    expect(page.locator('.sidebar-logout')).to_be_visible()
    page.screenshot(path=str(ROOT / 'test-artifacts' / 'dashboard-updated.png'), full_page=True)
    page.locator('.sidebar-logout button').click()
    page.wait_for_url('**/accounts/login/')
    assert not errors, errors
    browser.close()
    print('PASS: reference layouts, mobile widths, email login, password toggle, four dashboard cards and sidebar logout.')
