"""Run against a local development server. Creates isolated browser_* accounts."""
import os
import uuid
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault('PLAYWRIGHT_BROWSERS_PATH', str(ROOT / '.playwright'))
ARTIFACTS = ROOT / 'test-artifacts'
ARTIFACTS.mkdir(exist_ok=True)
BASE = os.getenv('SMOKE_BASE_URL', 'http://127.0.0.1:8011')

def register(page, username, password):
    page.goto(BASE + '/accounts/register/')
    assert 'EIEAAS' in page.title(), 'The URL must point to the EIEAAS development server.'
    for name, value in {'username':username, 'email':username+'@example.com', 'password1':password, 'password2':password}.items():
        page.locator(f'[name="{name}"]').fill(value)
    page.get_by_role('button', name='Sign Up', exact=True).click()
    if page.locator('.errorlist').count():
        raise AssertionError(page.locator('.errorlist').all_text_contents())
    page.wait_for_url(BASE + '/')
    page.wait_for_load_state('networkidle')

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    context = browser.new_context(viewport={'width':1440, 'height':1000})
    page = context.new_page()
    errors, dialogs = [], []
    page.on('pageerror', lambda error: (errors.append(str(error)), print('JavaScript:', error, flush=True)))
    page.on('dialog', lambda dialog: (dialogs.append(dialog.message), print('Dialog:', dialog.message, flush=True), dialog.accept()))
    username, password = 'browser_' + uuid.uuid4().hex[:10], 'Browser-unique-password-831!'
    register(page, username, password)
    expect(page.locator('#stats')).to_contain_text('Total invoices')

    page.locator('[data-page="profile"]').click()
    page.locator('#profileForm [name="name"]').fill('Browser Verification Studio')
    page.locator('#profileForm [name="email"]').fill('studio@example.com')
    page.locator('#profileForm [name="bank_name"]').fill('Demo Bank')
    page.locator('#logo').set_input_files(str(ROOT / 'assets' / 'dashboard-invoicing-illustration.png'))
    page.locator('#profileForm button').click()
    page.wait_for_load_state('networkidle')
    expect(page.locator('#sidebarBusiness')).to_have_text('Browser Verification Studio')
    expect(page.locator('#sidebarAvatar img')).to_be_visible()

    page.locator('[data-page="settings"]').click()
    page.locator('#settingsForm [name="vat"]').fill('15')
    page.locator('#settingsForm button').click()
    page.wait_for_load_state('networkidle')

    page.locator('[data-page="customers"]').click()
    page.locator('#customers .welcome button').click()
    page.locator('#customerForm [name="name"]').fill('Browser Client')
    page.locator('#customerForm [name="business"]').fill('Client Company')
    page.locator('#customerForm [name="email"]').fill('client@example.com')
    page.locator('#customerForm button[type="button"] + button').click()
    expect(page.locator('#customerModal')).not_to_have_class('modal open')
    expect(page.locator('#customerBody')).to_contain_text('Browser Client')

    page.locator('[data-page="create"]').click()
    page.locator('#invoiceCustomer').select_option(label='Client Company')
    page.locator('.line-row .desc').fill('Design work')
    page.locator('.line-row .qty').fill('2')
    page.locator('.line-row .unit').fill('100.10')
    page.get_by_role('button', name='Add item').click()
    page.locator('.line-row .desc').nth(1).fill('Hosting')
    page.locator('.line-row .qty').nth(1).fill('3')
    page.locator('.line-row .unit').nth(1).fill('20')
    page.locator('#discount').fill('10')
    expect(page.locator('#total')).to_have_text('R289.23')
    page.screenshot(path=str(ARTIFACTS / 'invoice-editor.png'), full_page=True)
    page.get_by_role('button', name='Save Invoice', exact=True).click()
    expect(page.locator('#invoiceBody')).to_contain_text('R289.23')
    page.reload()
    page.wait_for_load_state('networkidle')
    state = page.request.get(BASE + '/api/state/').json()
    invoice = state['invoices'][0]
    assert invoice['total'] == '289.23' and len(invoice['items']) == 2
    invoice_id = invoice['id']

    page.locator('[data-page="payments"]').click()
    page.locator('#payments .welcome button').click()
    page.locator('#paymentForm [name="amount"]').fill('100')
    page.locator('#paymentForm .modal-actions .btn').last.click()
    expect(page.locator('#paymentModal')).not_to_have_class('modal open')
    expect(page.locator('#paymentBody')).to_contain_text('R100.00')
    invoice = page.request.get(BASE + f'/api/invoices/{invoice_id}/').json()
    assert invoice['balance_due'] == '189.23' and invoice['status'] == 'Unpaid'
    page.locator('#payments .welcome button').click()
    expect(page.locator('#paymentForm [name="amount"]')).to_have_value('189.23')
    page.locator('#paymentForm .modal-actions .btn').last.click()
    expect(page.locator('#paymentModal')).not_to_have_class('modal open')
    invoice = page.request.get(BASE + f'/api/invoices/{invoice_id}/').json()
    assert invoice['balance_due'] == '0.00' and invoice['status'] == 'Paid'

    page.locator('[data-page="reports"]').click()
    expect(page.locator('#reportStats')).to_contain_text('R289.23')
    page.locator('[data-page="invoices"]').click()
    page.locator('#invoiceBody [title="Preview"]').click()
    expect(page.locator('#invoicePaper')).to_contain_text('289.23')
    expect(page.locator('#invoicePaper')).to_contain_text('Paid')
    with page.expect_popup() as popup:
        page.locator('#previewModal').get_by_role('button', name='Print / Save PDF').click()
    document = popup.value
    document.wait_for_load_state('networkidle')
    expect(document.locator('.invoice-paper')).to_contain_text('Browser Verification Studio')
    document.emulate_media(media='print')
    expect(document.locator('.print-document')).to_be_visible()
    expect(document.locator('.print-controls')).not_to_be_visible()
    document.pdf(path=str(ARTIFACTS / 'invoice.pdf'), format='A4')
    document.screenshot(path=str(ARTIFACTS / 'invoice-print.png'), full_page=True)
    document.close()
    page.locator('#previewModal .close').click()
    page.locator('[data-page="dashboard"]').click()
    page.screenshot(path=str(ARTIFACTS / 'dashboard.png'), full_page=True)

    page.set_viewport_size({'width':390, 'height':844})
    page.screenshot(path=str(ARTIFACTS / 'mobile.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile dashboard overflows viewport'
    page.locator('#menu').click()
    page.locator('[data-page="create"]').click()
    assert page.locator('#invoiceCustomer').is_visible()
    page.screenshot(path=str(ARTIFACTS / 'mobile-editor.png'), full_page=True)
    assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'), 'Mobile editor overflows viewport'

    other = browser.new_context()
    other_page = other.new_page()
    register(other_page, 'browser_other_'+uuid.uuid4().hex[:8], password)
    assert other_page.request.get(BASE + f'/api/invoices/{invoice_id}/').status == 404
    assert other_page.request.get(BASE + f'/invoices/{invoice_id}/print/').status == 404
    assert other_page.request.get(BASE + '/api/state/').json()['invoices'] == []
    other.close()

    page.locator('#menu').click()
    page.get_by_role('button', name='Log out', exact=True).click()
    page.wait_for_url('**/accounts/login/')
    page.locator('[name="username"]').fill(username)
    page.locator('[name="password"]').fill(password)
    page.get_by_role('button', name='Log In', exact=True).click()
    page.wait_for_url(BASE + '/')
    page.wait_for_load_state('networkidle')
    assert not errors, errors
    assert dialogs == ['Business profile saved.', 'Settings saved.'], dialogs
    assert page.request.get(BASE + '/static/billing/app.css').status == 200
    assert page.request.get(BASE + '/static/assets/dashboard-invoicing-illustration.png').status == 200
    browser.close()
    print('PASS: registration/login/logout, profile, customer, two-item invoice, Decimal totals, persistence, partial/final payment, reports, PDF, mobile layout, ownership and static files. No JavaScript errors.')
