from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI()

app.add_middleware(CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/")
def root():
    return {"status": "SCM API is running", "endpoint": "/query?q=your question"}

# Load CSV once when server starts
df = pd.read_csv("supplier_performance_data.csv")
df["Region"] = df["Region"].fillna("NA")
df["Active_Disruptions"] = df["Active_Disruptions"].fillna("")

@app.get("/query")
def query(q: str):
    question = q.lower()

    # Tier-3 with disruptions
    if "tier-3" in question and any(w in question for w in ["disruption","active","flag"]):
        mask = (df["Contract_Tier"] == "Tier-3") & (df["Active_Disruptions"] != "")
        result = df[mask][["Supplier_ID","Supplier_Name","Risk_Level","Active_Disruptions"]]\
                   .drop_duplicates("Supplier_ID")
        return {"count": len(result), "suppliers": result.to_dict("records")}

    # Volume rebate
    if "rebate" in question:
        mask = ((df["Contract_Tier"] == "Tier-1") &
                (df["OTD_Rate_Pct"] >= 93) &
                (df["Defect_Rate_Pct"] < 0.5) &
                (df["Sustainability_Score"] >= 85))
        names = df[mask]["Supplier_Name"].drop_duplicates().sort_values().tolist()
        return {"count": len(names), "suppliers": names}

    # Region spend
    if any(w in question for w in ["region","concentration","spend","highest po"]):
        spend = df.groupby("Region")["PO_Value_USD"].sum()
        total = spend.sum()
        return {"total_usd": round(total, 2),
                "by_region": {r: {"total": round(v,2), "pct": round(v/total*100,2)}
                              for r,v in spend.items()}}

    # Watch list
    if any(w in question for w in ["watch list","swl","watch-list"]):
        mask = df["Compliance_Score"] < 60
        result = df[mask][["Supplier_ID","Supplier_Name","Compliance_Score"]]\
                   .drop_duplicates("Supplier_ID").sort_values("Compliance_Score")
        return {"count": len(result), "suppliers": result.to_dict("records")}

    # Defect by category
    if "defect" in question and "categor" in question:
        result = df.groupby("Product_Category").agg(
            avg_defect=("Defect_Rate_Pct","mean"),
            po_count=("PO_ID","count")
        ).round(3).sort_values("avg_defect", ascending=False)
        return {"categories": result.to_dict("index")}

    # Supplier lookup by name
    if "supplier" in question or "sup-" in question:
        for token in question.split():
            if token.startswith("sup-"):
                rows = df[df["Supplier_ID"].str.lower() == token]\
                         .drop_duplicates("Supplier_ID")
                if len(rows): return {"supplier": rows.to_dict("records")}
        # Search by name fragment
        for word in question.split():
            if len(word) > 4:
                rows = df[df["Supplier_Name"].str.lower().str.contains(word)]\
                         .drop_duplicates("Supplier_ID")
                if len(rows): return {"suppliers": rows.to_dict("records")}

    # Country / region filter
    if any(w in question for w in ["finland","china","germany","india","apac","emea","latam"]):
        for country in df["Country"].dropna().unique():
            if country.lower() in question:
                rows = df[df["Country"] == country]\
                         .drop_duplicates("Supplier_ID")[["Supplier_ID","Supplier_Name","Contract_Tier","Risk_Level"]]
                return {"country": country, "count": len(rows), "suppliers": rows.to_dict("records")}
        for region in ["APAC","EMEA","LATAM","NA"]:
            if region.lower() in question:
                rows = df[df["Region"] == region]\
                         .drop_duplicates("Supplier_ID")[["Supplier_ID","Supplier_Name","Contract_Tier","Risk_Level"]]
                return {"region": region, "count": len(rows), "suppliers": rows.to_dict("records")}

    # OTD filter
    if "otd" in question or "on-time" in question or "on time" in question:
        if "below" in question or "less" in question or "under" in question:
            for num in ["70","75","80","85","90","93"]:
                if num in question:
                    rows = df[df["OTD_Rate_Pct"] < float(num)]\
                             .drop_duplicates("Supplier_ID")[["Supplier_ID","Supplier_Name","OTD_Rate_Pct","Contract_Tier"]]
                    return {"count": len(rows), "suppliers": rows.to_dict("records")}

    # Lead time
    if "lead time" in question:
        rows = df[["Supplier_ID","Supplier_Name","Lead_Time_Days"]]\
                 .drop_duplicates("Supplier_ID")\
                 .sort_values("Lead_Time_Days", ascending=False)\
                 .head(10)
        return {"top_10_longest_lead_times": rows.to_dict("records")}

    # High risk suppliers
    if "high risk" in question:
        rows = df[df["Risk_Level"] == "High"]\
                 .drop_duplicates("Supplier_ID")[["Supplier_ID","Supplier_Name","Compliance_Score","Active_Disruptions"]]
        return {"count": len(rows), "suppliers": rows.to_dict("records")}

    # Tier count
    if "how many" in question and "tier" in question:
        counts = df.drop_duplicates("Supplier_ID").groupby("Contract_Tier").size()
        return {"tier_counts": counts.to_dict()}

    return {"message": "Query received but no specific filter matched. Try asking about: disruptions, rebate, region spend, watch list, defect rates, specific supplier names, country, OTD, lead time, risk level, or tier counts."}