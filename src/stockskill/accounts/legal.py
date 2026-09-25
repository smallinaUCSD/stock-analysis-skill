"""Terms of Service and Privacy Policy.

Bump the version string whenever the text changes materially: users who
accepted an older version are asked to accept again at their next sign-in.
Operator details come from the environment so they can be filled in without
editing code (STOCKSKILL_OPERATOR, STOCKSKILL_CONTACT_EMAIL).

These are drafts written to be sensible for a free research tool. Have a
lawyer review them before charging money or advertising the service.
"""

from __future__ import annotations

import html
import os

TERMS_VERSION = "2026-09-25"
PRIVACY_VERSION = "2026-09-25"
EFFECTIVE = "September 25, 2026"


def operator() -> str:
    return os.environ.get("STOCKSKILL_OPERATOR") or "SMI Investments"


def contact() -> str:
    return os.environ.get("STOCKSKILL_CONTACT_EMAIL") or ""


def _contact_html() -> str:
    c = contact()
    return (f'<a href="mailto:{html.escape(c)}">{html.escape(c)}</a>' if c
            else "the contact address shown on our website")


def terms_body() -> str:
    op, c = html.escape(operator()), _contact_html()
    return f"""
<p class="lg-eff">Effective {EFFECTIVE} · Version {TERMS_VERSION}</p>
<div class="lg-callout"><b>Please read this carefully.</b> It includes a binding arbitration agreement and a
waiver of class actions and jury trials (section 13), which affect how disputes are resolved. You can opt out
of arbitration within 30 days. Nothing on this service is financial advice.</div>

<h2>1. Agreement</h2>
<p>These Terms of Service ("Terms") are a legal agreement between you and {op} ("we", "us", "our") covering
your use of this website, its web applications, alerts and related services (the "Service"). By creating an
account, checking the box to accept these Terms, or using the Service, you agree to these Terms and to our
<a href="/privacy">Privacy Policy</a>. If you do not agree, do not use the Service.</p>

<h2>2. Eligibility</h2>
<p>You must be at least 18 years old and able to form a binding contract to use the Service. By using it you
confirm that you are, and that the information you give us (including your date of birth) is accurate.</p>

<h2>3. Not investment advice</h2>
<p><b>The Service is for information and education only. It is not investment, financial, legal, tax or
accounting advice, and it is not a recommendation or offer to buy, sell or hold any security, fund,
cryptocurrency or other asset.</b></p>
<ul>
<li>We are not a registered investment adviser, broker-dealer, financial planner or fiduciary, and we are not
registered with the SEC, FINRA or any state securities regulator. We do not know your financial situation,
goals or risk tolerance, and nothing we show is tailored to you, even when it uses your watchlist or
settings.</li>
<li>Signals, scores, valuations, fair-value estimates, forecasts, price ranges, "breakouts", option ideas,
screens, alerts and backtests are the output of mathematical models applied to historical and third-party
data. Models are simplifications, can be wrong, and historical or simulated results do not predict future
results. Many of our own tests show signals that did not beat the market; we say so where we know it.</li>
<li>Information about trades by members of Congress, executives, the President or investment funds comes
from public filings that are delayed (often by weeks or months), may be incomplete or misread, and is not a
basis for trading.</li>
<li>Investing involves risk, including the loss of all of the money you invest. Leveraged and inverse funds,
options and cryptocurrencies can lose value very quickly and are not suitable for most people.</li>
<li>You are solely responsible for your investment decisions and their results. Consult a licensed
professional before making financial decisions.</li>
</ul>

<h2>4. Market data and third-party content</h2>
<p>Prices, fundamentals, filings, news, economic data and other content come from third parties (for example
the SEC, the Bureau of Labor Statistics, the U.S. Treasury, Nasdaq and commercial data providers). Data may be
delayed, incomplete, inaccurate or unavailable, and we do not verify it. We are not responsible for
third-party content or websites we link to. Data is provided for your personal, non-commercial use only.</p>

<h2>5. Your account</h2>
<p>You are responsible for keeping your password, passkeys and sign-in methods secure and for everything that
happens under your account. Tell us promptly if you suspect unauthorized use. You may not share your account,
create accounts by automated means, or impersonate anyone. We may refuse, suspend or close accounts at our
discretion, including for violations of these Terms.</p>

<h2>6. Acceptable use</h2>
<p>You agree not to: (a) scrape, crawl, copy, resell, redistribute or build a competing product from the
Service or its data; (b) access it through automated means other than a normal browser, except where we
publish an interface for that purpose; (c) interfere with or overload the Service, probe it for
vulnerabilities, or bypass security or rate limits; (d) upload malicious code; (e) use it for anything
unlawful, including market manipulation or insider trading; or (f) help anyone else do these things.</p>

<h2>7. Fees and plans</h2>
<p>The Service is currently free. Paid plans may be offered in the future; if so, their prices and terms will
be presented to you before you are charged, and you will not be charged without your agreement.</p>

<h2>8. Intellectual property</h2>
<p>The Service, its software, design, text and graphics are owned by us or our licensors and protected by law.
We grant you a limited, personal, revocable, non-transferable licence to use the Service for your own
non-commercial purposes under these Terms. Feedback you send us may be used by us without obligation to
you.</p>

<h2>9. Availability and changes</h2>
<p>We may change, suspend or discontinue any part of the Service at any time, with or without notice. The
Service may be unavailable because of maintenance, outages or events outside our control, and alerts may be
late or not delivered. Do not rely on the Service for time-sensitive decisions.</p>

<h2>10. Disclaimer of warranties</h2>
<p class="lg-caps">To the fullest extent permitted by law, the Service and all content are provided "as is" and
"as available", without warranties of any kind, express, implied or statutory, including warranties of
accuracy, completeness, timeliness, merchantability, fitness for a particular purpose, title and
non-infringement. We do not warrant that the Service will be uninterrupted, secure or error-free, or that any
information, signal or result is correct.</p>

<h2>11. Limitation of liability</h2>
<p class="lg-caps">To the fullest extent permitted by law, we and our owners, employees, agents and licensors
will not be liable for any indirect, incidental, special, consequential, exemplary or punitive damages, or for
any loss of profits, trading or investment losses, lost data or goodwill, arising from or related to the
Service or these Terms, whether in contract, tort (including negligence) or any other theory, even if advised
of the possibility. Our total liability for all claims relating to the Service is limited to the greater of
(a) the amount you paid us in the 12 months before the claim or (b) US $50.</p>
<p>Some jurisdictions do not allow certain exclusions or limits, so some of the above may not apply to you. In
that case our liability is limited to the smallest amount the law permits.</p>

<h2>12. Indemnity</h2>
<p>You agree to defend, indemnify and hold us harmless from claims, losses and expenses (including reasonable
legal fees) arising from your use of the Service, your violation of these Terms, or your violation of any law
or the rights of others.</p>

<h2>13. Dispute resolution: arbitration and class-action waiver</h2>
<p><b>Informal resolution first.</b> Before filing a claim, you agree to contact us at {c} and try to resolve
the dispute informally for at least 30 days.</p>
<p><b>Binding individual arbitration.</b> Except as stated below, any dispute, claim or controversy between
you and us arising out of or relating to the Service or these Terms ("Dispute") will be resolved by binding
arbitration administered by the American Arbitration Association under its Consumer Arbitration Rules, rather
than in court. The arbitrator's decision is final and may be entered in any court with jurisdiction. The
Federal Arbitration Act governs this section.</p>
<p><b>Class-action and jury-trial waiver.</b> You and we each agree to bring claims only in an individual
capacity, and not as a plaintiff or class member in any class, collective, consolidated or representative
proceeding. The arbitrator may not consolidate claims or award relief on behalf of anyone other than you.
<b>You and we each waive the right to a jury trial.</b></p>
<p><b>Exceptions.</b> Either party may bring an individual claim in small-claims court if it qualifies, and
either party may seek an injunction in court to protect intellectual property.</p>
<p><b>30-day opt-out.</b> You may opt out of this arbitration agreement by emailing {c} within 30 days of
first accepting these Terms, with your name, the email on your account and a clear statement that you opt out
of arbitration. Opting out does not affect any other part of these Terms.</p>
<p><b>Time limit.</b> To the extent permitted by law, any claim must be brought within one year after it
arises, or it is permanently barred.</p>

<h2>14. Governing law</h2>
<p>These Terms are governed by the laws of the State of California and applicable federal law, without regard
to conflict-of-law rules. For any matter not subject to arbitration, you and we consent to the exclusive
jurisdiction of the state and federal courts located in San Diego County, California.</p>

<h2>15. Termination</h2>
<p>You can stop using the Service and delete your account at any time from your account settings. We may
suspend or end your access at any time. Sections that by their nature should survive (including 3, 4, 8 and
10 through 16) survive termination.</p>

<h2>16. General</h2>
<p>These Terms and the Privacy Policy are the entire agreement between you and us about the Service. If any
part is found unenforceable, the rest remains in effect and that part is enforced to the maximum extent
permitted. Our failure to enforce a provision is not a waiver. You may not assign these Terms; we may assign
them in connection with a merger, acquisition or sale of assets. We are not liable for delays or failures
caused by events beyond our reasonable control. We may update these Terms; if the changes are material we
will ask you to accept them again before you continue using the Service.</p>

<h2>17. Contact</h2>
<p>Questions about these Terms: {c}.</p>
"""


def privacy_body() -> str:
    op, c = html.escape(operator()), _contact_html()
    return f"""
<p class="lg-eff">Effective {EFFECTIVE} · Version {PRIVACY_VERSION}</p>
<div class="lg-callout"><b>In short:</b> we collect what we need to run your account and personalize your
watchlist. We do not sell your personal information, we do not use advertising or tracking cookies, and you
can delete your account and its data at any time.</div>

<h2>1. Who we are</h2>
<p>{op} ("we", "us") operates this service. This policy explains what personal information we collect, how we
use and share it, and the choices and rights you have. It applies together with our
<a href="/terms">Terms of Service</a>.</p>

<h2>2. Information we collect</h2>
<p><b>Information you give us</b></p>
<ul>
<li><b>Account details:</b> your email address and, if you create a password, a salted one-way hash of it
(we never store or see your actual password).</li>
<li><b>Profile:</b> first and last name, date of birth (used to confirm you are 18 or older), and optionally
your gender.</li>
<li><b>Preferences:</b> the kind of investor you are, your experience level, how you heard about us, the
sectors and indices you chose, and your watchlist.</li>
<li><b>Messages</b> you send us, such as support requests.</li>
</ul>
<p><b>Information from sign-in providers.</b> If you choose "Sign in with Google", Google shares your name,
email address, whether it is verified, and a Google account identifier. We do not receive your Google
password or access to your Gmail, contacts or files.</p>
<p><b>Passkeys.</b> If you create a passkey, we store only its public key, an identifier and a usage counter.
Your fingerprint, face or device PIN never leave your device and are never sent to us.</p>
<p><b>Information collected automatically.</b> Our servers record technical information needed to operate and
secure the Service: IP address, browser type, the pages and features requested, and error logs. We use one
essential cookie to keep you signed in. We do not use advertising cookies, cross-site trackers or third-party
analytics.</p>
<p>We do not collect Social Security numbers, bank or brokerage credentials, or payment card details.</p>

<h2>3. How we use information</h2>
<ul>
<li>To create and secure your account, sign you in, and prevent fraud and abuse.</li>
<li>To personalize the Service, such as building your watchlist from the sectors you pick.</li>
<li>To operate, maintain, debug and improve the Service, including aggregated statistics that do not
identify you.</li>
<li>To send you service messages, such as security notices or changes to our terms. We will ask before
sending marketing email, and you can unsubscribe at any time.</li>
<li>To comply with law and enforce our Terms.</li>
</ul>
<p>We do not use your information to make automated decisions that have legal or similarly significant
effects on you.</p>

<h2>4. How we share information</h2>
<p><b>We do not sell your personal information and do not share it for cross-context behavioural
advertising.</b> We share it only:</p>
<ul>
<li>with service providers that host or deliver the Service for us (for example our hosting and network
providers), who may use it only to provide those services;</li>
<li>with Google, only if you choose to sign in with Google;</li>
<li>when required by law, subpoena or court order, or to protect the rights, property or safety of us, our
users or others;</li>
<li>in connection with a merger, acquisition or sale of assets, in which case this policy continues to apply
to your information; and</li>
<li>with your consent.</li>
</ul>
<p>Market data requests we make to data providers do not include your personal information.</p>

<h2>5. Retention</h2>
<p>We keep account information while your account is open. When you delete your account we delete your
profile, watchlist and passkeys immediately from the live database, and from backups within 30 days. Server
logs are kept for up to 90 days. We may keep limited records longer where the law requires, such as a record
that you accepted our Terms.</p>

<h2>6. Your choices and rights</h2>
<ul>
<li>View and edit your profile and watchlist, and remove passkeys, in account settings.</li>
<li>Delete your account and its data at any time from account settings.</li>
<li>Ask us for a copy of your information, or ask us to correct or delete it, by contacting {c}.</li>
</ul>
<p><b>California residents.</b> Under the California Consumer Privacy Act (as amended by the CPRA) you have the
right to know what personal information we collect, use and disclose; to access, correct and delete it; to
opt out of its sale or sharing (we do not sell or share it); to limit use of sensitive personal information
(we use it only to provide the Service); and not to be discriminated against for exercising these rights. In
the past 12 months we collected the categories described in section 2 (identifiers, personal
characteristics such as age and gender, internet activity, and inferences such as your investor type) for the
purposes in section 3, and disclosed them only as described in section 4. You or an authorized agent can make
a request by contacting {c}; we will verify your identity before acting on it.</p>
<p><b>Other locations.</b> Depending on where you live you may have similar rights, including the right to
object to or restrict processing and to complain to a data-protection authority. Contact us to exercise
them.</p>

<h2>7. Security</h2>
<p>We use HTTPS encryption, hash passwords, store passkeys as public keys only, and limit access to our
systems. No method of transmission or storage is completely secure, so we cannot guarantee absolute security.
Keep your sign-in methods private and tell us if you suspect unauthorized access.</p>

<h2>8. Children</h2>
<p>The Service is only for people 18 and older. We do not knowingly collect information from anyone under 18;
if we learn we have, we will delete it.</p>

<h2>9. International users</h2>
<p>The Service is operated from the United States, and your information is processed and stored there. By
using the Service you understand that your information will be transferred to the United States.</p>

<h2>10. Changes</h2>
<p>We may update this policy. If the changes are material we will tell you and, where required, ask for your
consent before they apply to you. The effective date at the top shows when it last changed.</p>

<h2>11. Contact</h2>
<p>Questions or requests about your privacy: {c}.</p>
"""
