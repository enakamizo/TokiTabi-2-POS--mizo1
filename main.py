from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import mysql.connector
from typing import List  # 追加
from fastapi.middleware.cors import CORSMiddleware  # CORSのインポート

app = FastAPI()

# CORS設定を追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # どのオリジンからでもアクセスを許可
    allow_credentials=True,
    allow_methods=["*"],  # すべてのHTTPメソッドを許可
    allow_headers=["*"],  # すべてのHTTPヘッダーを許可
)

import os
from dotenv import load_dotenv

# .envファイルから環境変数を読み込む
load_dotenv()

# デバッグ用に環境変数の内容を出力
print(f"Connecting to MySQL with: host={os.getenv('DB_HOST')}, user={os.getenv('DB_USER')}, port={os.getenv('DB_PORT')}")

db = mysql.connector.connect(
    host=os.getenv('DB_HOST'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD'),
    database=os.getenv('DB_NAME'),
    #port=int(os.getenv('DB_PORT', 3306))   # ポートも含める
)

cursor = db.cursor(dictionary=True)

# リクエストボディのモデル
class ProductRequest(BaseModel):
    code: str

# 商品検索API
@app.get("/product/{code}")
def get_product(code: str):
    cursor.execute("SELECT * FROM products WHERE CODE = %s", (code,))
    product = cursor.fetchone()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product

# 購入リクエスト用のデータモデル
class PurchaseItem(BaseModel):
    product_id: int
    quantity: int

class PurchaseRequest(BaseModel):
    items: List[PurchaseItem]

# 購入API
@app.post("/purchase")
def purchase(request: PurchaseRequest):
    try:
        # 1. 新しい取引を作成
        cursor.execute("INSERT INTO transactions (TOTAL_AMT) VALUES (%s)", (0,))
        db.commit()
        transaction_id = cursor.lastrowid  # 取引IDを取得
        
        total_amount = 0
        
        # 2. 取引の詳細を保存
        for item in request.items:
            cursor.execute("SELECT * FROM products WHERE PRD_ID = %s", (item.product_id,))
            product = cursor.fetchone()
            if not product:
                raise HTTPException(status_code=404, detail=f"Product ID {item.product_id} not found")

            # 商品の価格と数量を計算
            item_total = product["PRICE"] * item.quantity
            total_amount += item_total

            # 取引明細にデータを保存
            cursor.execute("""
                INSERT INTO transaction_details (TRD_ID, PRD_ID, PRD_CODE, PRD_NAME, PRD_PRICE) 
                VALUES (%s, %s, %s, %s, %s)
            """, (
                transaction_id, 
                product["PRD_ID"], 
                product["CODE"], 
                product["NAME"], 
                product["PRICE"]
            ))
            db.commit()

        # 3. 合計金額を取引テーブルに保存
        cursor.execute("UPDATE transactions SET TOTAL_AMT = %s WHERE TRD_ID = %s", (total_amount, transaction_id))
        db.commit()

        # 合計金額を返す
        return {"transaction_id": transaction_id, "total_amount": total_amount}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# FastAPIアプリケーションの起動
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

