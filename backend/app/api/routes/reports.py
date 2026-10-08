from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from app.api.deps import db_session, require_permission
from app.models.master import User
from app.schemas.api import DateRangeIn, ReportOut
from app.services.reports import ReportService

router = APIRouter(prefix="/reports", tags=["reports"])

@router.post("/sales-summary", response_model=ReportOut)
def sales_summary(payload: DateRangeIn, user: User = Depends(require_permission("REPORT_VIEW")), db: Session = Depends(db_session)):
    if payload.end < payload.start:
        raise HTTPException(400, "End date cannot be before start date")
    s = ReportService(db).sales_summary(branch_id=user.branch_id, start=payload.start, end=payload.end)
    is_admin = user.role.code.upper() == "ADMIN"
    return ReportOut(start=payload.start, end=payload.end, sales_count=s.sales_count, sales_total=s.sales_total, cash_total=s.cash_total, card_total=s.card_total, online_total=s.online_total, cost_total=s.cost_total if is_admin else None, gross_profit=s.gross_profit if is_admin else None, expenses_total=s.expenses_total if is_admin else None, other_income_total=s.other_income_total if is_admin else None, net_profit=s.net_profit if is_admin else None, refunds_total=s.refunds_total if is_admin else None, return_charge_total=s.return_charge_total if is_admin else None)

@router.post('/target-progress')
def target_progress(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start: raise HTTPException(400, 'End date cannot be before start date')
    from app.services.targets import TargetService
    return [ {'target_id':str(x.target_id),'target_type':x.target_type,'target_value':x.target_value if user.role.code.upper()=='ADMIN' or x.target_type not in {'ITEM_SALES_PROFIT','REPAIR_PROFIT'} else None,'achieved':x.achieved if user.role.code.upper()=='ADMIN' or x.target_type not in {'ITEM_SALES_PROFIT','REPAIR_PROFIT'} else None,'percentage':x.percentage if user.role.code.upper()=='ADMIN' or x.target_type not in {'ITEM_SALES_PROFIT','REPAIR_PROFIT'} else None} for x in TargetService(db).progress(branch_id=user.branch_id,start=payload.start,end=payload.end) ]


@router.post('/target-history')
def target_history(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start: raise HTTPException(400, 'End date cannot be before start date')
    if user.role.code.upper() != 'ADMIN': raise HTTPException(403, 'Admin only')
    from app.models.master import TargetProgressSnapshot
    rows=db.scalars(select(TargetProgressSnapshot).where(TargetProgressSnapshot.branch_id==user.branch_id, TargetProgressSnapshot.period_end.between(payload.start,payload.end)).order_by(TargetProgressSnapshot.period_end.desc(),TargetProgressSnapshot.target_type)).all()
    return [{'snapshot_id':str(x.id),'target_id':str(x.target_id),'target_version':x.target_version,'target_type':x.target_type,'target_value':x.target_value,'achieved':x.achieved_value,'percentage':x.percentage,'period_type':x.period_type,'period_start':x.period_start,'period_end':x.period_end,'captured_at':x.captured_at,'captured_by':str(x.captured_by) if x.captured_by else None} for x in rows]


@router.post('/cashiers')
def cashier_summary(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start: raise HTTPException(400, 'End date cannot be before start date')
    if user.role.code.upper() != 'ADMIN': raise HTTPException(403, 'Admin only')
    return [ {'cashier_id':str(x.cashier_id),'cashier_name':x.cashier_name,'sales_count':x.sales_count,'sales_total':x.sales_total,'cost_total':x.cost_total,'gross_profit':x.gross_profit} for x in ReportService(db).cashier_summary(branch_id=user.branch_id,start=payload.start,end=payload.end) ]

@router.post('/cash-in-hands')
def cash_in_hands(payload: DateRangeIn, user: User = Depends(require_permission('CASH_HANDS_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start: raise HTTPException(400, 'End date cannot be before start date')
    value = ReportService(db).cash_in_hands(branch_id=user.branch_id, start=payload.start, end=payload.end)
    return {'start':payload.start,'end':payload.end,'cash_in_hands':value}

@router.post('/comparison')
def report_comparison(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start: raise HTTPException(400, 'End date cannot be before start date')
    from datetime import timedelta
    span=(payload.end-payload.start).days+1
    prev_end=payload.start-timedelta(days=1); prev_start=prev_end-timedelta(days=span-1)
    current=ReportService(db).sales_summary(branch_id=user.branch_id,start=payload.start,end=payload.end)
    previous=ReportService(db).sales_summary(branch_id=user.branch_id,start=prev_start,end=prev_end)
    return {'current':{'start':payload.start,'end':payload.end,'sales_total':current.sales_total,'gross_profit':current.gross_profit,'sales_count':current.sales_count,'net_profit':current.net_profit},'previous':{'start':prev_start,'end':prev_end,'sales_total':previous.sales_total,'gross_profit':previous.gross_profit,'sales_count':previous.sales_count,'net_profit':previous.net_profit}}

@router.post('/stock-age')
def stock_age(payload: DateRangeIn, user: User = Depends(require_permission('STOCK_VIEW')), db: Session = Depends(db_session)):
    from app.models.inventory import PurchaseLot
    from app.models.master import Item
    from datetime import date
    as_of=payload.end
    rows=db.execute(select(PurchaseLot,Item).join(Item,Item.id==PurchaseLot.item_id).where(PurchaseLot.branch_id==user.branch_id,PurchaseLot.remaining_quantity>0).order_by(PurchaseLot.lot_date,Item.item_code)).all()
    return [{'item_id':str(item.id),'item_code':item.item_code,'description':item.description,'lot_id':str(lot.id),'lot_date':lot.lot_date,'remaining_quantity':lot.remaining_quantity,'unit_cost':lot.unit_cost,'age_days':(as_of-lot.lot_date).days} for lot,item in rows]

@router.post('/purchases')
def purchase_report(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    from app.models.inventory import Purchase, PurchaseLine
    rows=db.execute(select(Purchase.purchase_date,Purchase.reference_no,PurchaseLine.item_id,PurchaseLine.quantity,PurchaseLine.unit_cost).join(PurchaseLine,PurchaseLine.purchase_id==Purchase.id).where(Purchase.branch_id==user.branch_id,Purchase.purchase_date.between(payload.start,payload.end)).order_by(Purchase.purchase_date)).all()
    return [{'purchase_date':r.purchase_date,'reference_no':r.reference_no,'item_id':str(r.item_id),'quantity':r.quantity,'unit_cost':r.unit_cost} for r in rows]

@router.post('/repairs')
def repair_report(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    from app.models.sales import Repair, RepairPayment
    payment_total=select(func.coalesce(func.sum(RepairPayment.amount),0)).where(RepairPayment.repair_id==Repair.id).scalar_subquery()
    rows=db.scalars(select(Repair).where(Repair.branch_id==user.branch_id,func.date(Repair.date_in).between(payload.start,payload.end)).order_by(Repair.date_in)).all()
    return [{'repair_id':str(r.id),'repair_no':r.repair_no,'date_in':r.date_in,'status':r.status,'total_amount':r.total_amount,'labour_amount':r.labour_amount,'payments_total':db.scalar(select(func.coalesce(func.sum(RepairPayment.amount),0)).where(RepairPayment.repair_id==r.id)) or 0} for r in rows]

@router.post('/warranty')
def warranty_report(payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    from app.models.warranty import WarrantyClaim
    rows=db.scalars(select(WarrantyClaim).where(WarrantyClaim.branch_id==user.branch_id,func.date(WarrantyClaim.created_at).between(payload.start,payload.end)).order_by(WarrantyClaim.created_at)).all()
    return [{'claim_id':str(x.id),'claim_no':x.claim_no,'item_id':str(x.item_id),'quantity':x.holding_quantity,'decision':x.admin_decision,'outcome':x.replacement_outcome,'created_at':x.created_at} for x in rows]

@router.post('/cash-drawer')
def cash_drawer_report(payload: DateRangeIn, user: User = Depends(require_permission('DAY_MANAGE')), db: Session = Depends(db_session)):
    from app.models.finance import DaySession, DayEnd
    rows=db.execute(select(DaySession,DayEnd).join(DayEnd,DayEnd.day_session_id==DaySession.id).where(DaySession.branch_id==user.branch_id,DaySession.business_date.between(payload.start,payload.end)).order_by(DaySession.business_date)).all()
    return [{'business_date':day.business_date,'opening_cash':day.opening_cash,'expected_cash':end.expected_cash,'actual_cash':end.actual_cash,'difference':end.difference,'reload_total':end.reload_total,'reason':end.reason} for day,end in rows]

@router.post('/export/{report_type}/{file_format}')
def export_report(report_type: str, file_format: str, payload: DateRangeIn, user: User = Depends(require_permission('REPORT_VIEW')), db: Session = Depends(db_session)):
    if payload.end < payload.start:
        raise HTTPException(400,'End date cannot be before start date')
    fmt=file_format.lower()
    if fmt not in {'xlsx','pdf'}:
        raise HTTPException(400,'Format must be xlsx or pdf')
    report_type=report_type.lower()
    is_admin=user.role.code.upper()=='ADMIN'
    rows: list[tuple[str, object]] = []

    if report_type=='profit':
        if not is_admin: raise HTTPException(403,'Admin only')
        s=ReportService(db).sales_summary(branch_id=user.branch_id,start=payload.start,end=payload.end)
        rows=[('Sales Profit',s.gross_profit),('Repair Profit',s.repair_profit),('Other Income',s.other_income_total),('Return Charge Income',s.return_charge_total),('Expenses',s.expenses_total),('Damage/Loss',s.damage_loss_total),('Net Profit',s.net_profit)]
    elif report_type=='sales':
        s=ReportService(db).sales_summary(branch_id=user.branch_id,start=payload.start,end=payload.end)
        rows=[('Sales Total',s.sales_total),('Bills',s.sales_count),('Cash',s.cash_total),('Card',s.card_total),('Online',s.online_total)]
        if is_admin:
            rows += [('Cost',s.cost_total),('Gross Profit',s.gross_profit),('Refunds',s.refunds_total),('Return Charges',s.return_charge_total),('Expenses',s.expenses_total),('Other Income',s.other_income_total),('Net Profit',s.net_profit)]
    elif report_type=='cash-in-hands':
        if not is_admin: raise HTTPException(403,'Admin only')
        rows=[('Cash In Hands',ReportService(db).cash_in_hands(branch_id=user.branch_id,start=payload.start,end=payload.end))]
    elif report_type=='purchases':
        if not is_admin: raise HTTPException(403,'Admin only')
        from app.models.inventory import Purchase, PurchaseLine
        rows=[('Date', 'Reference', 'Item ID', 'Quantity', 'Unit Cost')]
        data=db.execute(select(Purchase.purchase_date,Purchase.reference_no,PurchaseLine.item_id,PurchaseLine.quantity,PurchaseLine.unit_cost).join(PurchaseLine,PurchaseLine.purchase_id==Purchase.id).where(Purchase.branch_id==user.branch_id,Purchase.purchase_date.between(payload.start,payload.end)).order_by(Purchase.purchase_date)).all()
        rows += [(str(r.purchase_date),r.reference_no or '',str(r.item_id),r.quantity,r.unit_cost) for r in data]
    elif report_type=='repairs':
        from app.models.sales import Repair, RepairPayment
        rows=[('Repair No','Date In','Status','Total Amount','Labour Amount','Payments Total')]
        repairs=db.scalars(select(Repair).where(Repair.branch_id==user.branch_id,func.date(Repair.date_in).between(payload.start,payload.end)).order_by(Repair.date_in)).all()
        rows += [(r.repair_no,str(r.date_in),r.status,r.total_amount,r.labour_amount,db.scalar(select(func.coalesce(func.sum(RepairPayment.amount),0)).where(RepairPayment.repair_id==r.id)) or 0) for r in repairs]
    elif report_type=='warranty':
        from app.models.warranty import WarrantyClaim
        rows=[('Claim No','Created','Item ID','Quantity','Decision','Outcome')]
        claims=db.scalars(select(WarrantyClaim).where(WarrantyClaim.branch_id==user.branch_id,func.date(WarrantyClaim.created_at).between(payload.start,payload.end)).order_by(WarrantyClaim.created_at)).all()
        rows += [(x.claim_no,str(x.created_at),str(x.item_id),x.holding_quantity,x.admin_decision or '',x.replacement_outcome or '') for x in claims]
    elif report_type=='stock':
        from app.models.master import Item
        from app.models.inventory import StockMovement
        rows=[('Item Code','Description','Stock','Active')]
        data=db.execute(select(Item.item_code,Item.description,func.coalesce(func.sum(StockMovement.quantity_delta),0),Item.is_active).outerjoin(StockMovement,(StockMovement.item_id==Item.id)&(StockMovement.branch_id==user.branch_id)).where(Item.is_active.is_(True)).group_by(Item.id).order_by(Item.item_code)).all()
        rows += [(r[0],r[1],r[2],r[3]) for r in data]
    elif report_type=='cash-drawer':
        if not is_admin: raise HTTPException(403,'Admin only')
        from app.models.finance import DaySession, DayEnd
        rows=[('Business Date','Opening Cash','Expected Cash','Actual Cash','Difference','Reload Total','Reason')]
        data=db.execute(select(DaySession,DayEnd).join(DayEnd,DayEnd.day_session_id==DaySession.id).where(DaySession.branch_id==user.branch_id,DaySession.business_date.between(payload.start,payload.end)).order_by(DaySession.business_date)).all()
        rows += [(str(day.business_date),day.opening_cash,end.expected_cash,end.actual_cash,end.difference,end.reload_total,end.reason or '') for day,end in data]
    else:
        raise HTTPException(400,'Unsupported report export type')

    from io import BytesIO
    from fastapi.responses import StreamingResponse
    filename=f'lovely-tech-{report_type}-{payload.start}-to-{payload.end}.{fmt}'
    buf=BytesIO()
    if fmt=='xlsx':
        from openpyxl import Workbook
        wb=Workbook(); ws=wb.active; ws.title='Report'
        for row in rows: ws.append([float(v) if hasattr(v,'as_tuple') else v for v in row])
        wb.save(buf); media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.lib.styles import getSampleStyleSheet
        doc=SimpleDocTemplate(buf,pagesize=landscape(A4)); styles=getSampleStyleSheet()
        data=[[str(v) for v in row] for row in rows]
        table=Table(data,repeatRows=1)
        table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,colors.black),('BACKGROUND',(0,0),(-1,0),colors.lightgrey),('FONTSIZE',(0,0),(-1,-1),8)]))
        doc.build([Paragraph(f'Lovely Tech POS — {report_type.replace("-"," ").title()}',styles['Title']),table]); media='application/pdf'
    buf.seek(0)
    return StreamingResponse(buf,media_type=media,headers={'Content-Disposition':f'attachment; filename="{filename}"'})

