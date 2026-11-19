import io
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from storage import get_all_comparison

def generate_comparison_excel():
    wb = openpyxl.Workbook()
    
    ws_comp = wb.active
    ws_comp.title = "Comparison"
    ws_comp.views.sheetView[0].showGridLines = True
    
    font_title = Font(name="Calibri", size=15, bold=True, color="1F497D")
    font_subtitle = Font(name="Calibri", size=10, italic=True, color="595959")
    font_tbl_hdr = Font(name="Calibri", size=10, bold=True, color="FFFFFF")
    font_bold = Font(name="Calibri", size=10, bold=True, color="000000")
    font_savings = Font(name="Calibri", size=10, bold=True, color="1E4620")
    
    fill_navy = PatternFill(start_color="1F497D", end_color="1F497D", fill_type="solid")
    fill_zebra = PatternFill(start_color="F2F5F9", end_color="F2F5F9", fill_type="solid")
    
    thin_border = Side(border_style="thin", color="D9D9D9")
    thick_bottom = Side(border_style="medium", color="1F497D")
    border_data = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thin_border)
    border_hdr = Border(left=thin_border, right=thin_border, top=thin_border, bottom=thick_bottom)
    
    ws_comp.merge_cells("A1:K1")
    ws_comp["A1"] = "Supplier Price Comparison (ဖုန်းဈေးနှုန်း နှိုင်းယှဉ်ချက်ဇယား)"
    ws_comp["A1"].font = font_title
    
    ws_comp.merge_cells("A2:K2")
    ws_comp["A2"] = "Suppliers: LK Mobile, Sky Mobile, Supplier C | Banking Payment Only (No Fee) | Unit: MMK"
    ws_comp["A2"].font = font_subtitle
    
    headers = [
        "No.", "Model Name", "RAM / Storage", 
        "LK Mobile (MMK)", "Sky Mobile (MMK)", "Supplier C (MMK)", 
        "Lowest Price (အနိမ့်ဆုံး)", "Cheapest Supplier (အသက်သာဆုံး)", "Savings (သက်သာငွေ)", "Notes"
    ]
    
    for col_idx, h in enumerate(headers, 1):
        cell = ws_comp.cell(row=4, column=col_idx, value=h)
        cell.font = font_tbl_hdr
        cell.fill = fill_navy
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border_hdr
        
    rows = get_all_comparison()
    for i, r in enumerate(rows):
        curr_r = 5 + i
        ws_comp.cell(row=curr_r, column=1, value=i+1).alignment = Alignment(horizontal="center")
        ws_comp.cell(row=curr_r, column=2, value=r["model"]).alignment = Alignment(horizontal="left")
        ws_comp.cell(row=curr_r, column=3, value=r["ram_storage"]).alignment = Alignment(horizontal="center")
        
        p_dict = r.get("all_prices", {})
        c_lk = ws_comp.cell(row=curr_r, column=4, value=p_dict.get("LK Mobile"))
        c_sky = ws_comp.cell(row=curr_r, column=5, value=p_dict.get("Sky Mobile"))
        c_c = ws_comp.cell(row=curr_r, column=6, value=p_dict.get("Supplier C"))
        
        for c in [c_lk, c_sky, c_c]:
            if isinstance(c.value, (int, float)):
                c.number_format = "#,##0"
                c.alignment = Alignment(horizontal="right")
            else:
                c.alignment = Alignment(horizontal="center")
                
        c_low = ws_comp.cell(row=curr_r, column=7, value=r["lowest_price"])
        c_low.number_format = "#,##0"
        c_low.alignment = Alignment(horizontal="right")
        c_low.font = font_bold
        
        ws_comp.cell(row=curr_r, column=8, value=r["cheapest_supplier"]).alignment = Alignment(horizontal="center")
        
        c_sav = ws_comp.cell(row=curr_r, column=9, value=r["savings"])
        c_sav.number_format = "#,##0"
        c_sav.alignment = Alignment(horizontal="right")
        c_sav.font = font_savings
        
        ws_comp.cell(row=curr_r, column=10, value="").alignment = Alignment(horizontal="left")
        
        for col_c in range(1, 11):
            cell_item = ws_comp.cell(row=curr_r, column=col_c)
            cell_item.border = border_data
            if i % 2 == 1:
                cell_item.fill = fill_zebra
                
    widths = {1: 6, 2: 28, 3: 15, 4: 18, 5: 18, 6: 18, 7: 20, 8: 24, 9: 18, 10: 30}
    for col_idx, w in widths.items():
        ws_comp.column_dimensions[get_column_letter(col_idx)].width = w
        
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()
