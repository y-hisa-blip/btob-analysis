#!/usr/bin/env python3
"""
BtoB分析ダッシュボード デプロイスクリプト
CSVを読み込んで分析 → HTMLを生成 → Netlifyにデプロイ
"""

import csv
import json
import requests
from datetime import datetime
from pathlib import Path
import os

# ===== 設定 =====
CSV_FILE = '/Users/yusukehisashima/Desktop/BBJ_顧客情報_260218.csv'
OUTPUT_HTML = '/Users/yusukehisashima/Desktop/ビール記事/btob_analysis.html'
NETLIFY_SITE_ID = '7d7d617a-eaeb-41e7-ac7e-b9bbca41cebd'
NETLIFY_API_TOKEN = os.getenv('NETLIFY_API_TOKEN')  # 環境変数から取得

if not NETLIFY_API_TOKEN:
    raise ValueError("環境変数 NETLIFY_API_TOKEN が設定されていません")

# ===== ビジネスタイプ分類 =====
def classify_business_type(shop_name):
    """店舗名からビジネスタイプを判定"""
    keywords = {
        'ブルワリー': ['brewery', 'brewing', 'brewpub', 'ビール醸造', 'ブルワリー'],
        'ビアバー・ビール専門店': ['ビアバー', 'ビール専門', 'beer bar', '麦酒'],
        '飲食店': ['焼肉', '居酒屋', 'レストラン', 'cafe', 'カフェ', 'bar', 'パブ', '食堂', 'タパス', 'ピザ', 'うどん'],
        '酒屋・酒販店': ['酒屋', '酒販', '酒のスマイル'],
        '小売・ショップ': ['shopify', 'ショップ', 'shop', 'eコマース'],
    }

    manual_override = {
        'HEAVY SASORI BREWING': '飲食店',
        'みゃーブリュー': '飲食店',
        'やきにく善～zen～?肉と麦酒と日本酒?': '飲食店',
        'ＩＳＬＡＮＤＢＲＥＷＩＮＧ株式会社 Island brewing': '飲食店',
        'ジェフ沖縄株式会社': '飲食店',
        '株式会社ドリームメイカー クオッカ': '飲食店',
        '株式会社ライブポート SUMER': '飲食店',
        '株式会社　TABANA UNLOCK Brew BASE': '飲食店',
        '株式会社谷口 びあマ': '飲食店',
        '永山不動産株式会社 337 Ale': 'ブルワリー',
    }

    if shop_name in manual_override:
        return manual_override[shop_name]

    shop_lower = shop_name.lower()
    for btype, kws in keywords.items():
        for kw in kws:
            if kw.lower() in shop_lower:
                return btype

    return 'その他法人'

# ===== データ読み込みと分析 =====
def load_and_analyze(csv_file):
    """CSVを読み込んで分析"""
    orders = {}
    shops_info = {}

    try:
        with open(csv_file, encoding='cp932') as f:
            reader = csv.reader(f)
            header = next(reader)

            for row in reader:
                if len(row) < 7:
                    continue

                date, shop, pref, product, price, qty, subtotal = row[:7]

                # 南島酒販を除外
                if shop == '南島酒販株式会社':
                    continue

                # 注文キー：(日付, 店舗)
                order_key = (date, shop)

                try:
                    price_val = float(price)
                    qty_val = int(qty)
                    subtotal_val = float(subtotal)
                except:
                    continue

                # 注文情報を集約
                if order_key not in orders:
                    orders[order_key] = {
                        'date': date,
                        'shop': shop,
                        'pref': pref,
                        'total': 0,
                        'items': 0
                    }

                orders[order_key]['total'] += subtotal_val
                orders[order_key]['items'] += qty_val

                # 店舗情報
                if shop not in shops_info:
                    shops_info[shop] = {
                        'pref': pref,
                        'type': classify_business_type(shop),
                        'orders': 0,
                        'sales': 0,
                        'first_order': date,
                        'last_order': date
                    }

                shops_info[shop]['orders'] += 1
                shops_info[shop]['sales'] += subtotal_val
                shops_info[shop]['last_order'] = date

        return list(orders.values()), shops_info

    except Exception as e:
        print(f"CSV读み込みエラー: {e}")
        raise

# ===== HTML生成 =====
def generate_html(orders, shops_info):
    """HTMLダッシュボードを生成"""

    # 分析期間を判定
    dates = [o['date'] for o in orders]
    dates.sort()
    first_date = dates[0] if dates else '2026/1/1'
    last_date = dates[-1] if dates else '2026/3/10'

    # KPI計算
    total_sales = sum(o['total'] for o in orders)
    total_orders = len(orders)
    total_shops = len(shops_info)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BtoB分析ダッシュボード - AGARIHAMA BREWERY</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@3.9.1/dist/chart.min.js"></script>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        header {{
            background: linear-gradient(135deg, #1a1a1a 0%, #333 100%);
            color: white;
            padding: 30px;
            border-radius: 8px;
            margin-bottom: 30px;
        }}
        header h1 {{ font-size: 28px; margin-bottom: 10px; }}
        header p {{ font-size: 14px; opacity: 0.9; }}

        .kpi-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .kpi-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        .kpi-label {{ font-size: 12px; color: #666; text-transform: uppercase; margin-bottom: 8px; }}
        .kpi-value {{ font-size: 28px; font-weight: bold; color: #333; }}

        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            position: relative;
            height: 400px;
        }}
        .chart-title {{ font-size: 16px; font-weight: bold; margin-bottom: 20px; color: #333; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}
        th {{
            background: #f9f9f9;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            color: #666;
            border-bottom: 1px solid #ddd;
        }}
        td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}
        tr:hover {{ background: #fafafa; }}

        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 600;
        }}
        .badge-blue {{ background: #e3f2fd; color: #1565c0; }}
        .badge-green {{ background: #e8f5e9; color: #2e7d32; }}
        .badge-orange {{ background: #fff3e0; color: #e65100; }}

        footer {{
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            color: #999;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🍺 BtoB分析ダッシュボード</h1>
            <p>AGARIHAMA BREWERY - 顧客分析 | 更新：{datetime.now().strftime('%Y年%m月%d日')}</p>
        </header>

        <div class="kpi-grid">
            <div class="kpi-card">
                <div class="kpi-label">期間売上</div>
                <div class="kpi-value">¥{total_sales:,.0f}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">注文件数</div>
                <div class="kpi-value">{total_orders}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">取引先数</div>
                <div class="kpi-value">{total_shops}</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-label">平均注文額</div>
                <div class="kpi-value">¥{total_sales/total_orders:,.0f}</div>
            </div>
        </div>

        <h2 style="margin-bottom: 20px; color: #333;">📊 ビジネスタイプ別分析</h2>
        <table>
            <thead>
                <tr>
                    <th>ビジネスタイプ</th>
                    <th>取引先数</th>
                    <th>注文件数</th>
                    <th>売上</th>
                    <th>平均注文額</th>
                </tr>
            </thead>
            <tbody>
"""

    # ビジネスタイプ別集計
    by_type = {}
    for shop, info in shops_info.items():
        btype = info['type']
        if btype not in by_type:
            by_type[btype] = {'shops': 0, 'orders': 0, 'sales': 0}
        by_type[btype]['shops'] += 1
        by_type[btype]['orders'] += info['orders']
        by_type[btype]['sales'] += info['sales']

    for btype in sorted(by_type.keys()):
        data = by_type[btype]
        avg = data['sales'] / data['orders'] if data['orders'] > 0 else 0
        html += f"""                <tr>
                    <td><span class="badge badge-blue">{btype}</span></td>
                    <td>{data['shops']}</td>
                    <td>{data['orders']}</td>
                    <td>¥{data['sales']:,.0f}</td>
                    <td>¥{avg:,.0f}</td>
                </tr>
"""

    html += """            </tbody>
        </table>

        <h2 style="margin-top: 40px; margin-bottom: 20px; color: #333;">🏆 トップ顧客（売上順）</h2>
        <table>
            <thead>
                <tr>
                    <th>順位</th>
                    <th>店舗名</th>
                    <th>都道府県</th>
                    <th>タイプ</th>
                    <th>注文件数</th>
                    <th>売上</th>
                </tr>
            </thead>
            <tbody>
"""

    # トップ顧客
    sorted_shops = sorted(shops_info.items(), key=lambda x: x[1]['sales'], reverse=True)
    for rank, (shop, info) in enumerate(sorted_shops[:20], 1):
        type_badge = {
            'ブルワリー': 'badge-blue',
            'ビアバー・ビール専門店': 'badge-green',
            '飲食店': 'badge-orange',
            '酒屋・酒販店': 'badge-blue',
            '小売・ショップ': 'badge-green',
            'その他法人': 'badge-blue'
        }.get(info['type'], 'badge-blue')

        html += f"""                <tr>
                    <td><strong>#{rank}</strong></td>
                    <td>{shop}</td>
                    <td>{info['pref']}</td>
                    <td><span class="badge {type_badge}">{info['type']}</span></td>
                    <td>{info['orders']}</td>
                    <td>¥{info['sales']:,.0f}</td>
                </tr>
"""

    html += """            </tbody>
        </table>

        <footer>
            <p>更新日時: """ + datetime.now().strftime('%Y年%m月%d日 %H:%M:%S') + """</p>
            <p>このダッシュボードはPythonスクリプトで自動生成されています</p>
        </footer>
    </div>
</body>
</html>
"""

    return html

# ===== Netlify にデプロイ =====
def deploy_to_netlify(html_content):
    """Netlify にHTMLファイルをアップロード"""

    # Netlify API エンドポイント
    url = f'https://api.netlify.com/api/v1/sites/{NETLIFY_SITE_ID}/files/btob_analysis.html'

    headers = {
        'Authorization': f'Bearer {NETLIFY_API_TOKEN}',
        'Content-Type': 'text/html'
    }

    try:
        response = requests.put(url, data=html_content.encode('utf-8'), headers=headers)

        if response.status_code in [200, 201]:
            print(f"✅ デプロイ成功！")
            print(f"URL: https://{NETLIFY_SITE_ID}.netlify.app/btob_analysis.html")
            return True
        else:
            print(f"❌ デプロイ失敗: {response.status_code}")
            print(f"レスポンス: {response.text}")
            return False

    except Exception as e:
        print(f"❌ エラー: {e}")
        return False

# ===== メイン処理 =====
if __name__ == '__main__':
    print("🔄 分析を開始します...")

    try:
        orders, shops_info = load_and_analyze(CSV_FILE)
        print(f"✓ CSV読み込み完了: {len(orders)}件の注文, {len(shops_info)}社の顧客")

        html = generate_html(orders, shops_info)
        print(f"✓ HTML生成完了")

        # ローカルに保存
        with open(OUTPUT_HTML, 'w', encoding='utf-8') as f:
            f.write(html)
        print(f"✓ ローカルファイル保存: {OUTPUT_HTML}")

        # Netlify にデプロイ
        print(f"🚀 Netlify にデプロイ中...")
        if deploy_to_netlify(html):
            print("✨ 完了！")
        else:
            print("⚠️  ローカルファイルは保存されていますが、Netlifyへのアップロードに失敗しました")

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
        import traceback
        traceback.print_exc()
