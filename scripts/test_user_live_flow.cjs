const puppeteer = require('puppeteer-core');
const fs = require('fs');
const path = require('path');

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const ARTIFACT_DIR = '/Users/munonguyen/.gemini/antigravity-ide/brain/fb02f5e5-5769-468e-b5f0-5313a7441d04';
const SCREENSHOT_DIR = path.join(ARTIFACT_DIR, 'user_test_screenshots');

if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

(async () => {
  console.log('🚀 KHỞI ĐỘNG TRÌNH DUYỆT CHROME ĐỂ ĐÓNG VAI USER KIỂM TRA THỰC ĐỊA...');

  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--window-size=1440,900',
    ],
    defaultViewport: { width: 1440, height: 900 },
  });

  const context = browser.defaultBrowserContext();
  
  // Set initial location: Phố Bà La, Đình Bảng, Từ Sơn (21.1078, 105.9561)
  await context.overridePermissions('https://medguard.bookingcare.shop', ['geolocation']);
  
  const page = await browser.newPage();
  await page.setGeolocation({ latitude: 21.1078, longitude: 105.9561, accuracy: 12 });

  const testReport = {
    test1_gps_tu_son: null,
    test2_gps_hanoi: null,
    test3_address_search: null,
    test4_categories_scan: null,
    test5_poi_detail_card: null,
  };

  try {
    // ------------------------------------------------------------------------
    // KỊCH BẢN 1: USER TRUY CẬP TRANG VÀ BẬT ĐỊNH VỊ GPS THỰC TẾ TẠI TỪ SƠN
    // ------------------------------------------------------------------------
    console.log('\n===============================================================');
    console.log('TEST 1: User truy cập trang, cấp quyền GPS thực tế tại Từ Sơn (21.1078, 105.9561)');
    console.log('===============================================================');

    await page.goto('https://medguard.bookingcare.shop/?view=navigation', {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });

    await delay(2500);

    // Kiểm tra xem Modal có hiển thị không
    const isModalVisible = await page.$('.nav-permission-modal');
    console.log('Modal xác nhận vị trí có xuất hiện:', !!isModalVisible);

    if (isModalVisible) {
      console.log('User bấm nút: "Lấy Chính Xác Vị Trí GPS Của Tôi (Khuyến Nghị)"');
      await page.click('.btn-grant-gps');
      await delay(3000);
    }

    // Đọc thông tin Origin Pill trên thanh Topbar
    const originPillData = await page.evaluate(() => {
      const pill = document.querySelector('.nav-origin-pill');
      const title = document.querySelector('.origin-title')?.innerText?.trim();
      const coords = document.querySelector('.origin-coords')?.innerText?.trim();
      const badge = document.querySelector('.origin-type-badge')?.innerText?.trim();
      const isGpsActive = pill?.classList.contains('gps-active');
      return { title, coords, badge, isGpsActive };
    });

    console.log('Kết quả Origin Pill sau khi lấy GPS:', originPillData);

    // Mở drawer danh sách cơ sở y tế
    const drawerToggle = await page.$('.nav-drawer-toggle-btn');
    if (drawerToggle) {
      await drawerToggle.click();
      await delay(1200);
    }

    // Đọc danh sách POIs vừa quét
    const discoveredPois = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.poi-card-item'));
      return cards.map((c) => {
        const name = c.querySelector('.card-poi-name')?.innerText?.trim();
        const dist = c.querySelector('.dist-badge')?.innerText?.trim();
        const addr = c.querySelector('.card-poi-address')?.innerText?.trim();
        const badge = c.querySelector('.card-category-badge')?.innerText?.trim();
        return { name, dist, addr, badge };
      });
    });

    console.log(`Tìm thấy ${discoveredPois.length} cơ sở y tế quanh vị trí GPS Từ Sơn:`);
    discoveredPois.slice(0, 8).forEach((p, i) => {
      console.log(`  [${i + 1}] ${p.dist} | ${p.name} (${p.addr})`);
    });

    const shot1Path = path.join(SCREENSHOT_DIR, '01_user_gps_tu_son.png');
    await page.screenshot({ path: shot1Path, fullPage: false });
    console.log('Đã chụp ảnh kiểm chứng Test 1:', shot1Path);

    testReport.test1_gps_tu_son = {
      originPill: originPillData,
      poiCount: discoveredPois.length,
      samplePois: discoveredPois.slice(0, 5),
    };

    // ------------------------------------------------------------------------
    // KỊCH BẢN 2: USER THAY ĐỔI VỊ TRÍ GPS SANG HOÀN KIẾM, HÀ NỘI (21.0285, 105.8542)
    // ------------------------------------------------------------------------
    console.log('\n===============================================================');
    console.log('TEST 2: User di chuyển sang Hoàn Kiếm, Hà Nội (21.0285, 105.8542)');
    console.log('===============================================================');

    await page.setGeolocation({ latitude: 21.0285, longitude: 105.8542, accuracy: 8 });
    console.log('User bấm nút "Cập nhật GPS" trên Topbar...');
    await page.click('.gps-refresh-btn');
    await delay(3500);

    const hanoiOriginPill = await page.evaluate(() => {
      const title = document.querySelector('.origin-title')?.innerText?.trim();
      const coords = document.querySelector('.origin-coords')?.innerText?.trim();
      const badge = document.querySelector('.origin-type-badge')?.innerText?.trim();
      return { title, coords, badge };
    });

    console.log('Kết quả Origin Pill tại Hoàn Kiếm:', hanoiOriginPill);

    const hanoiPois = await page.evaluate(() => {
      const cards = Array.from(document.querySelectorAll('.poi-card-item'));
      return cards.map((c) => ({
        name: c.querySelector('.card-poi-name')?.innerText?.trim(),
        dist: c.querySelector('.dist-badge')?.innerText?.trim(),
        addr: c.querySelector('.card-poi-address')?.innerText?.trim(),
      }));
    });

    console.log(`Tìm thấy ${hanoiPois.length} cơ sở y tế tại Hoàn Kiếm, Hà Nội:`);
    hanoiPois.slice(0, 6).forEach((p, i) => {
      console.log(`  [${i + 1}] ${p.dist} | ${p.name} (${p.addr})`);
    });

    const shot2Path = path.join(SCREENSHOT_DIR, '02_user_gps_hanoi.png');
    await page.screenshot({ path: shot2Path, fullPage: false });
    console.log('Đã chụp ảnh kiểm chứng Test 2:', shot2Path);

    testReport.test2_gps_hanoi = {
      originPill: hanoiOriginPill,
      poiCount: hanoiPois.length,
      samplePois: hanoiPois.slice(0, 5),
    };

    // ------------------------------------------------------------------------
    // KỊCH BẢN 3: USER TÌM KIẾM ĐỊA CHỈ TỰ DO BẰNG TAY (GÕ "ĐÌNH BẢNG, TỪ SƠN")
    // ------------------------------------------------------------------------
    console.log('\n===============================================================');
    console.log('TEST 3: User bấm thanh vị trí và gõ tìm kiếm: "Đình Bảng, Từ Sơn"');
    console.log('===============================================================');

    // Click vào Origin Pill để mở modal chọn vị trí
    await page.click('.nav-origin-pill');
    await delay(800);

    // Gõ vào ô tìm kiếm địa chỉ
    console.log('User gõ "Dinh Bang, Tu Son" vào ô tìm kiếm...');
    await page.type('.modal-address-input', 'Dinh Bang, Tu Son', { delay: 60 });
    await delay(1200);

    // Kiểm tra dropdown gợi ý
    const suggestions = await page.evaluate(() => {
      const items = Array.from(document.querySelectorAll('.dropdown-item-btn'));
      return items.map((it) => ({
        title: it.querySelector('.item-title')?.innerText?.trim(),
        desc: it.querySelector('.item-desc')?.innerText?.trim(),
      }));
    });

    console.log(`Dropdown hiển thị ${suggestions.length} gợi ý địa chỉ:`, suggestions);

    if (suggestions.length > 0) {
      console.log('User click chọn gợi ý đầu tiên...');
      await page.click('.dropdown-item-btn:first-child');
      await delay(3500);
    }

    const customOriginPill = await page.evaluate(() => {
      const title = document.querySelector('.origin-title')?.innerText?.trim();
      const coords = document.querySelector('.origin-coords')?.innerText?.trim();
      const badge = document.querySelector('.origin-type-badge')?.innerText?.trim();
      return { title, coords, badge };
    });

    console.log('Kết quả Origin Pill sau khi chọn địa chỉ gõ tay:', customOriginPill);

    const shot3Path = path.join(SCREENSHOT_DIR, '03_user_address_search.png');
    await page.screenshot({ path: shot3Path, fullPage: false });
    console.log('Đã chụp ảnh kiểm chứng Test 3:', shot3Path);

    testReport.test3_address_search = {
      typedQuery: 'Dinh Bang, Tu Son',
      suggestionsCount: suggestions.length,
      originPillAfterSelect: customOriginPill,
    };

    // ------------------------------------------------------------------------
    // KỊCH BẢN 4: USER CHỌN CÁC DANH MỤC KHÁC NHAU (CLINIC, EMERGENCY, PHARMACY)
    // ------------------------------------------------------------------------
    console.log('\n===============================================================');
    console.log('TEST 4: User kiểm tra Quét Radar theo từng danh mục y tế');
    console.log('===============================================================');

    const categoriesTest = {};
    const chips = [
      { selector: '.category-chip:nth-child(2)', name: 'Điểm Y Tế (Clinic)' },
      { selector: '.category-chip:nth-child(3)', name: 'Cấp Cứu 24/7 (Emergency)' },
      { selector: '.category-chip:nth-child(1)', name: 'Điểm Bán Thuốc (Pharmacy)' },
    ];

    for (const chip of chips) {
      console.log(`\nUser bấm chọn: ${chip.name}`);
      await page.click(chip.selector);
      await delay(600);

      console.log('User bấm nút "Quét ... Quanh Bạn"');
      await page.click('.btn-trigger-radar-primary');

      // Đợi modal quét Radar chạy xong tiến trình 100%
      await delay(3800);

      const count = await page.evaluate(() => {
        return document.querySelectorAll('.poi-card-item').length;
      });

      const sampleNames = await page.evaluate(() => {
        const cards = Array.from(document.querySelectorAll('.poi-card-item')).slice(0, 4);
        return cards.map((c) => c.querySelector('.card-poi-name')?.innerText?.trim());
      });

      console.log(`Kết quả danh mục [${chip.name}]: Tìm thấy ${count} cơ sở:`, sampleNames);
      categoriesTest[chip.name] = { count, sampleNames };
    }

    const shot4Path = path.join(SCREENSHOT_DIR, '04_user_categories_scan.png');
    await page.screenshot({ path: shot4Path, fullPage: false });
    console.log('Đã chụp ảnh kiểm chứng Test 4:', shot4Path);

    testReport.test4_categories_scan = categoriesTest;

    // ------------------------------------------------------------------------
    // KỊCH BẢN 5: USER CHỌN 1 CƠ SỞ ĐỂ XEM CHI TIẾT & CHỈ ĐƯỜNG
    // ------------------------------------------------------------------------
    console.log('\n===============================================================');
    console.log('TEST 5: User chọn 1 cơ sở y tế để xem thẻ chi tiết & nút chỉ đường');
    console.log('===============================================================');

    // Click vào cơ sở đầu tiên trong danh sách
    await page.click('.poi-card-item:first-child');
    await delay(1500);

    const detailCardData = await page.evaluate(() => {
      const card = document.querySelector('.med-place-detail-card');
      if (!card) return null;
      const title = card.querySelector('.detail-poi-name')?.innerText?.trim();
      const dist = card.querySelector('.detail-dist-pill')?.innerText?.trim();
      const addr = card.querySelector('.detail-address-text')?.innerText?.trim();
      const specialty = card.querySelector('.specialty-text')?.innerText?.trim();
      const startNavBtn = card.querySelector('.btn-start-nav-primary')?.innerText?.trim();
      const callBtn = card.querySelector('.btn-call-facility')?.innerText?.trim();
      const gmapsLink = card.querySelector('.btn-open-gmaps-app')?.getAttribute('href');
      return { title, dist, addr, specialty, startNavBtn, callBtn, gmapsLink };
    });

    console.log('Thẻ Chi Tiết Địa Điểm hiển thị:', detailCardData);

    const shot5Path = path.join(SCREENSHOT_DIR, '05_user_poi_detail_card.png');
    await page.screenshot({ path: shot5Path, fullPage: false });
    console.log('Đã chụp ảnh kiểm chứng Test 5:', shot5Path);

    testReport.test5_poi_detail_card = detailCardData;

    console.log('\n===============================================================');
    console.log('🎉 TOÀN BỘ 5 KỊCH BẢN KIỂM THỬ TRẢI NGHIỆM USER ĐÃ HOÀN TẤT THÀNH CÔNG!');
    console.log('===============================================================');
    console.log('Dữ liệu tổng hợp:', JSON.stringify(testReport, null, 2));

  } catch (err) {
    console.error('Lỗi trong quá trình kiểm thử:', err);
  } finally {
    await browser.close();
  }
})();
