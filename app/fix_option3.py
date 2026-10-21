# Fix student name visibility and vertical layout in Option 3 (Royal Minimalist)
with open('app/templates/print_comparison.html', 'r', encoding='utf-8') as f:
    pc = f.read()

old_royal_css = '''/* DESIGN 3: ROYAL MINIMALIST */
    .card-royal {
      border-radius: 4.5mm;
      border: 1.5px solid #044332;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      background: #fafaf9;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2.2mm 3mm 2mm;
      position: relative;
    }
    .card-royal::before {
      content: "";
      position: absolute;
      top: 1mm; left: 1mm; right: 1mm; bottom: 1mm;
      border: 0.8px solid #d97706;
      border-radius: 3.8mm;
      pointer-events: none;
    }
    .card-royal .ry-header {
      display: flex; flex-direction: column; align-items: center;
      text-align: center; margin-bottom: 1.2mm; width: 100%;
    }
    .card-royal .ry-logo { width: 11mm; height: 11mm; margin-bottom: 0.6mm; }
    .card-royal .ry-logo img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-title-1,
    .card-royal .ry-title-2 {
      font-size: 9.2pt;
      font-weight: 900;
      color: #044332;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      line-height: 1.12;
    }
    .card-royal .ry-sub {
      font-size: 5pt;
      font-weight: 700;
      color: #b45309;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      margin-top: 0.4mm;
    }
    .card-royal .ry-divider {
      width: 24mm;
      height: 1px;
      background: #d97706;
      margin-top: 0.8mm;
    }
    .card-royal .ry-photo-box {
      width: 20mm; height: 23mm; border-radius: 3.5mm;
      border: 1.5px solid #044332; background: #fff;
      padding: 0.8mm;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .card-royal .ry-photo-inner {
      width: 100%; height: 100%; border-radius: 2.5mm;
      background: #cbd5e1; overflow: hidden;
      display: flex; align-items: center; justify-content: center;
    }
    .card-royal .ry-photo-inner img,
    .card-royal .ry-photo-box img { width: 100%; height: 100%; object-fit: cover; }
    .card-royal .ry-avatar svg,
    .card-royal .ry-photo-box svg { width: 13mm; height: 13mm; fill: #64748b; }
    .card-royal .ry-name {
      font-size: 9.5pt; font-weight: 800; color: #0f172a;
      text-align: center; margin-top: 1.4mm; max-width: 46mm;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.1;
    }
    .card-royal .ry-father {
      font-size: 5.5pt; color: #64748b; font-weight: 400;
      text-align: center; margin-top: 0.2mm;
    }
    .card-royal .ry-tags {
      display: flex; gap: 2mm; margin-top: 1.2mm; width: 100%; justify-content: center;
    }
    .card-royal .ry-tag {
      background: #f1f5f9; border: 1px solid #cbd5e1;
      border-radius: 1.5mm; padding: 0.6mm 2.5mm; text-align: center;
      display: flex; gap: 1.5mm; align-items: center;
    }
    .card-royal .ry-tag-lbl { font-size: 4.5pt; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .card-royal .ry-tag-val { font-size: 7pt; font-weight: 800; color: #044332; }
    .card-royal .ry-qr {
      width: 19.5mm; height: 19.5mm; border: 1px solid #d97706;
      border-radius: 2mm; padding: 0.6mm; background: #fff;
      display: flex; align-items: center; justify-content: center;
      margin-top: 1.2mm;
    }
    .card-royal .ry-qr img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-footer {
      font-size: 4.2pt; color: #64748b; font-weight: 600;
      letter-spacing: 0.6px; text-transform: uppercase; margin-top: 1.1mm;
    }'''

new_royal_css = '''/* DESIGN 3: ROYAL MINIMALIST */
    .card-royal {
      border-radius: 4.5mm;
      border: 1.5px solid #044332;
      box-shadow: 0 2px 8px rgba(0,0,0,0.06);
      background: #fafaf9;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 1.8mm 2.5mm 1.4mm;
      position: relative;
    }
    .card-royal::before {
      content: "";
      position: absolute;
      top: 1mm; left: 1mm; right: 1mm; bottom: 1mm;
      border: 0.8px solid #d97706;
      border-radius: 3.8mm;
      pointer-events: none;
    }
    .card-royal .ry-header {
      display: flex; flex-direction: column; align-items: center;
      text-align: center; margin-bottom: 0.8mm; width: 100%; flex-shrink: 0;
    }
    .card-royal .ry-logo { width: 9mm; height: 9mm; margin-bottom: 0.3mm; flex-shrink: 0; }
    .card-royal .ry-logo img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-title-1,
    .card-royal .ry-title-2 {
      font-size: 8.5pt;
      font-weight: 900;
      color: #044332;
      text-transform: uppercase;
      letter-spacing: 0.35px;
      line-height: 1.08;
    }
    .card-royal .ry-sub {
      font-size: 4.6pt;
      font-weight: 700;
      color: #b45309;
      letter-spacing: 0.7px;
      text-transform: uppercase;
      margin-top: 0.2mm;
    }
    .card-royal .ry-divider {
      width: 22mm;
      height: 1px;
      background: #d97706;
      margin-top: 0.5mm;
    }
    .card-royal .ry-photo-box {
      width: 19mm; height: 21.5mm; border-radius: 3.2mm;
      border: 1.5px solid #044332; background: #fff;
      padding: 0.6mm;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
      flex-shrink: 0;
      position: relative; z-index: 2;
    }
    .card-royal .ry-photo-inner {
      width: 100%; height: 100%; border-radius: 2.5mm;
      background: #cbd5e1; overflow: hidden;
      display: flex; align-items: center; justify-content: center;
    }
    .card-royal .ry-photo-inner img,
    .card-royal .ry-photo-box img { width: 100%; height: 100%; object-fit: cover; }
    .card-royal .ry-avatar svg,
    .card-royal .ry-photo-box svg { width: 12mm; height: 12mm; fill: #64748b; }
    .card-royal .ry-name {
      font-size: 9.6pt; font-weight: 800; color: #044332;
      text-align: center; margin-top: 1.2mm; max-width: 48mm;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.15;
      flex-shrink: 0; display: block; position: relative; z-index: 2;
    }
    .card-royal .ry-father {
      font-size: 5.2pt; color: #475569; font-weight: 400;
      text-align: center; margin-top: 0.2mm; line-height: 1;
      flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-tags {
      display: flex; gap: 2mm; margin-top: 1mm; width: 100%; justify-content: center;
      flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-tag {
      background: #f1f5f9; border: 1px solid #cbd5e1;
      border-radius: 1.5mm; padding: 0.5mm 2.2mm; text-align: center;
      display: flex; gap: 1.2mm; align-items: center;
    }
    .card-royal .ry-tag-lbl { font-size: 4.2pt; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .card-royal .ry-tag-val { font-size: 7pt; font-weight: 800; color: #044332; }
    .card-royal .ry-qr {
      width: 18.5mm; height: 18.5mm; border: 1px solid #d97706;
      border-radius: 2mm; padding: 0.6mm; background: #fff;
      display: flex; align-items: center; justify-content: center;
      margin-top: 1mm; flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-qr img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-footer {
      font-size: 4pt; color: #64748b; font-weight: 600;
      letter-spacing: 0.6px; text-transform: uppercase; margin-top: 0.8mm;
      flex-shrink: 0; position: relative; z-index: 2;
    }'''

if old_royal_css in pc:
    pc = pc.replace(old_royal_css, new_royal_css)
    print('Updated card-royal in print_comparison.html')
else:
    print('old_royal_css not found in print_comparison.html')

with open('app/templates/print_comparison.html', 'w', encoding='utf-8') as f:
    f.write(pc)

# Now update print_cards.html
with open('app/templates/print_cards.html', 'r', encoding='utf-8') as f:
    cards = f.read()

old_royal_cards_css = '''/* ========================================================
       DESIGN 3: ROYAL MINIMALIST (Ivory & Gold Crest)
       ======================================================== */
    .card-royal {
      border-radius: 4.5mm;
      border: 1.5px solid #044332;
      box-shadow: 0 4px 14px rgba(0,0,0,0.08);
      background: #fafaf9;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 2.2mm 3mm 2mm;
      position: relative;
    }
    .card-royal::before {
      content: "";
      position: absolute;
      top: 1mm; left: 1mm; right: 1mm; bottom: 1mm;
      border: 0.8px solid #d97706;
      border-radius: 3.8mm;
      pointer-events: none;
    }
    .card-royal .ry-header {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      margin-bottom: 1.2mm;
      width: 100%;
    }
    .card-royal .ry-logo {
      width: 11mm; height: 11mm;
      margin-bottom: 0.6mm;
    }
    .card-royal .ry-logo img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-title-1,
    .card-royal .ry-title-2 {
      font-size: 9.2pt;
      font-weight: 900;
      color: #044332;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      line-height: 1.12;
    }
    .card-royal .ry-sub {
      font-size: 5pt;
      font-weight: 700;
      color: #b45309;
      letter-spacing: 0.8px;
      text-transform: uppercase;
      margin-top: 0.4mm;
    }
    .card-royal .ry-divider {
      width: 24mm;
      height: 1px;
      background: #d97706;
      margin-top: 0.8mm;
    }
    .card-royal .ry-photo-box {
      width: 20mm; height: 23mm; border-radius: 3.5mm;
      border: 1.5px solid #044332; background: #fff;
      padding: 0.8mm;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }
    .card-royal .ry-photo-inner {
      width: 100%; height: 100%; border-radius: 2.5mm;
      background: #cbd5e1; overflow: hidden;
      display: flex; align-items: center; justify-content: center;
    }
    .card-royal .ry-photo-inner img,
    .card-royal .ry-photo-box img { width: 100%; height: 100%; object-fit: cover; }
    .card-royal .ry-avatar svg,
    .card-royal .ry-photo-box svg { width: 13mm; height: 13mm; fill: #64748b; }
    .card-royal .ry-name {
      font-size: 9.5pt; font-weight: 800; color: #0f172a;
      text-align: center; margin-top: 1.5mm; max-width: 46mm;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.1;
    }
    .card-royal .ry-father {
      font-size: 5.5pt; color: #64748b; font-weight: 400;
      text-align: center; margin-top: 0.3mm;
    }
    .card-royal .ry-tags {
      display: flex; gap: 2mm; margin-top: 1.4mm; width: 100%; justify-content: center;
    }
    .card-royal .ry-tag {
      background: #f1f5f9; border: 1px solid #cbd5e1;
      border-radius: 1.5mm; padding: 0.6mm 2.5mm; text-align: center;
      display: flex; gap: 1.5mm; align-items: center;
    }
    .card-royal .ry-tag-lbl { font-size: 4.5pt; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .card-royal .ry-tag-val { font-size: 7pt; font-weight: 800; color: #044332; }
    .card-royal .ry-qr {
      width: 19.5mm; height: 19.5mm; border: 1px solid #d97706;
      border-radius: 2mm; padding: 0.6mm; background: #fff;
      display: flex; align-items: center; justify-content: center;
      margin-top: 1.4mm;
    }
    .card-royal .ry-qr img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-footer {
      font-size: 4.2pt; color: #64748b; font-weight: 600;
      letter-spacing: 0.6px; text-transform: uppercase; margin-top: 1.2mm;
    }'''

new_royal_cards_css = '''/* ========================================================
       DESIGN 3: ROYAL MINIMALIST (Ivory & Gold Crest)
       ======================================================== */
    .card-royal {
      border-radius: 4.5mm;
      border: 1.5px solid #044332;
      box-shadow: 0 4px 14px rgba(0,0,0,0.08);
      background: #fafaf9;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 1.8mm 2.5mm 1.4mm;
      position: relative;
    }
    .card-royal::before {
      content: "";
      position: absolute;
      top: 1mm; left: 1mm; right: 1mm; bottom: 1mm;
      border: 0.8px solid #d97706;
      border-radius: 3.8mm;
      pointer-events: none;
    }
    .card-royal .ry-header {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
      margin-bottom: 0.8mm;
      width: 100%;
      flex-shrink: 0;
    }
    .card-royal .ry-logo {
      width: 9mm; height: 9mm;
      margin-bottom: 0.3mm;
      flex-shrink: 0;
    }
    .card-royal .ry-logo img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-title-1,
    .card-royal .ry-title-2 {
      font-size: 8.5pt;
      font-weight: 900;
      color: #044332;
      text-transform: uppercase;
      letter-spacing: 0.35px;
      line-height: 1.08;
    }
    .card-royal .ry-sub {
      font-size: 4.6pt;
      font-weight: 700;
      color: #b45309;
      letter-spacing: 0.7px;
      text-transform: uppercase;
      margin-top: 0.2mm;
    }
    .card-royal .ry-divider {
      width: 22mm;
      height: 1px;
      background: #d97706;
      margin-top: 0.5mm;
    }
    .card-royal .ry-photo-box {
      width: 19mm; height: 21.5mm; border-radius: 3.2mm;
      border: 1.5px solid #044332; background: #fff;
      padding: 0.6mm;
      display: flex; align-items: center; justify-content: center;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
      flex-shrink: 0;
      position: relative; z-index: 2;
    }
    .card-royal .ry-photo-inner {
      width: 100%; height: 100%; border-radius: 2.5mm;
      background: #cbd5e1; overflow: hidden;
      display: flex; align-items: center; justify-content: center;
    }
    .card-royal .ry-photo-inner img,
    .card-royal .ry-photo-box img { width: 100%; height: 100%; object-fit: cover; }
    .card-royal .ry-avatar svg,
    .card-royal .ry-photo-box svg { width: 12mm; height: 12mm; fill: #64748b; }
    .card-royal .ry-name {
      font-size: 9.6pt; font-weight: 800; color: #044332;
      text-align: center; margin-top: 1.2mm; max-width: 48mm;
      white-space: nowrap; overflow: hidden; text-overflow: ellipsis; line-height: 1.15;
      flex-shrink: 0; display: block; position: relative; z-index: 2;
    }
    .card-royal .ry-father {
      font-size: 5.2pt; color: #475569; font-weight: 400;
      text-align: center; margin-top: 0.2mm; line-height: 1;
      flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-tags {
      display: flex; gap: 2mm; margin-top: 1mm; width: 100%; justify-content: center;
      flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-tag {
      background: #f1f5f9; border: 1px solid #cbd5e1;
      border-radius: 1.5mm; padding: 0.5mm 2.2mm; text-align: center;
      display: flex; gap: 1.2mm; align-items: center;
    }
    .card-royal .ry-tag-lbl { font-size: 4.2pt; color: #64748b; font-weight: 600; text-transform: uppercase; }
    .card-royal .ry-tag-val { font-size: 7pt; font-weight: 800; color: #044332; }
    .card-royal .ry-qr {
      width: 18.5mm; height: 18.5mm; border: 1px solid #d97706;
      border-radius: 2mm; padding: 0.6mm; background: #fff;
      display: flex; align-items: center; justify-content: center;
      margin-top: 1mm; flex-shrink: 0; position: relative; z-index: 2;
    }
    .card-royal .ry-qr img { width: 100%; height: 100%; object-fit: contain; }
    .card-royal .ry-footer {
      font-size: 4pt; color: #64748b; font-weight: 600;
      letter-spacing: 0.6px; text-transform: uppercase; margin-top: 0.8mm;
      flex-shrink: 0; position: relative; z-index: 2;
    }'''

if old_royal_cards_css in cards:
    cards = cards.replace(old_royal_cards_css, new_royal_cards_css)
    print('Updated card-royal in print_cards.html')
else:
    print('old_royal_cards_css not found in print_cards.html')

with open('app/templates/print_cards.html', 'w', encoding='utf-8') as f:
    f.write(cards)

print('Option 3 fix complete!')
