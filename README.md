# HERO'S Classics

総合格闘技イベント『HERO'S』(2005〜2008年)の公式サイトを Wayback Machine のアーカイブから再構成した非公式の歴史資料サイトです。

本番URL: https://hero-s.k-1.info

## 構成

```
.
├── archive/          # 2005-2008 の原本 (Wayback から取得)
├── scripts/          # アーカイブ取得ツール (fetch.sh, convert_utf8.sh など)
├── extract.py        # archive/ から content/*.json を生成
├── build.py          # content/ + templates → dist/ を生成
├── dist/             # 生成物 (Amplify が配信)
├── amplify.yml       # AWS Amplify ビルド設定
└── .gitignore
```

## ローカルビルド

```
pip3 install --user beautifulsoup4 lxml
python3 extract.py          # archive/ → content/
python3 build.py            # content/ → dist/
cd dist && python3 -m http.server 8001
# → http://127.0.0.1:8001/
```

## Amplify デプロイ

本リポジトリをそのまま AWS Amplify Hosting に接続すれば `amplify.yml` に従ってビルド・配信されます。

- Build artifacts: `dist/`
- Build image: Amazon Linux 2023 (Python3 標準搭載)

## SEO 対策

- 各ページに `<meta viewport>` / `<meta description>` / `<link rel="canonical">` / OG タグを出力
- `sitemap.xml` と `robots.txt` をビルド時に生成
- 記事タイトルは本文先頭行から自動抽出
- 全ページレスポンシブ対応 (モバイルファーストの単一CSS)

## 注意事項

- HERO'S および関連する名称・画像は第三者の商標・著作物です。本サイトは **公開アーカイブを元にした非営利の歴史資料** として公開しています。権利者からの要請があれば該当コンテンツを削除します。
- `archive/` 以下の原本 HTML は履歴参照用で、配信対象ではありません。
- 2005〜2008 当時の動的機能 (投票 PHP など) は静的スナップショットとして保存されており、動作しません。
