from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from app.models.master import Target, TargetProgressSnapshot
from app.models.sales import Sale, SaleLine, Repair, RepairPart

@dataclass(frozen=True)
class TargetProgress:
    target_id: object; target_type: str; target_value: Decimal; achieved: Decimal; percentage: Decimal

class TargetService:
    def __init__(self, session: Session): self.session=session
    def snapshot_completed_periods(self, *, branch_id, as_of: date, captured_by=None):
        """Persist immutable progress snapshots for targets whose period has ended."""
        targets=self.session.scalars(select(Target).where(Target.branch_id==branch_id, Target.period_end<=as_of)).all()
        created=[]
        for t in targets:
            existing=self.session.scalar(select(TargetProgressSnapshot).where(TargetProgressSnapshot.target_id==t.id, TargetProgressSnapshot.target_version==t.version))
            if existing:
                continue
            progress=self.progress(branch_id=branch_id,start=t.period_start,end=t.period_end)
            current=next((x for x in progress if x.target_id==t.id),None)
            if current is None:
                continue
            row=TargetProgressSnapshot(target_id=t.id,branch_id=t.branch_id,target_version=t.version,target_type=t.target_type,target_value=current.target_value,achieved_value=current.achieved,percentage=current.percentage,period_type=t.period_type,period_start=t.period_start,period_end=t.period_end,captured_at=datetime.now(timezone.utc),captured_by=captured_by)
            self.session.add(row); created.append(row)
        self.session.flush()
        return created

    def progress(self, *, branch_id, start:date, end:date):
        targets=self.session.scalars(select(Target).where(Target.branch_id==branch_id,Target.period_start<=end,Target.period_end>=start)).all()
        out=[]
        for t in targets:
            code=t.target_type
            sales_q=select(func.coalesce(func.sum(Sale.grand_total),0)).where(Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')
            sales_cost_q=select(func.coalesce(func.sum(Sale.total_cost),0)).where(Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')
            if code=='SALES_AMOUNT': achieved=Decimal(self.session.scalar(sales_q) or 0)
            elif code=='ITEM_SALES_PROFIT': achieved=Decimal(self.session.scalar(sales_q) or 0)-Decimal(self.session.scalar(sales_cost_q) or 0)
            elif code=='BILLS_COUNT': achieved=Decimal(self.session.scalar(select(func.count(Sale.id)).where(Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')) or 0)
            elif code=='ITEMS_SOLD_COUNT': achieved=Decimal(self.session.scalar(select(func.coalesce(func.sum(SaleLine.quantity),0)).join(Sale,Sale.id==SaleLine.sale_id).where(Sale.branch_id==branch_id,func.date(Sale.sale_datetime).between(start,end),Sale.status=='COMPLETED')) or 0)
            elif code=='REPAIR_INCOME': achieved=Decimal(self.session.scalar(select(func.coalesce(func.sum(Repair.final_amount),0)).where(Repair.branch_id==branch_id,func.date(Repair.date_in).between(start,end),Repair.status.in_(['DELIVERED','RETURNED TO CUSTOMER']))) or 0)
            elif code=='REPAIR_PROFIT':
                achieved=Decimal(self.session.scalar(select(func.coalesce(func.sum(Repair.final_amount),0)).where(Repair.branch_id==branch_id,func.date(Repair.date_in).between(start,end),Repair.status.in_(['DELIVERED','RETURNED TO CUSTOMER']))) or 0)
                part_cost=Decimal(self.session.scalar(select(func.coalesce(func.sum(RepairPart.fifo_cost),0)).join(Repair,Repair.id==RepairPart.repair_id).where(Repair.branch_id==branch_id,func.date(Repair.date_in).between(start,end),Repair.status.in_(['DELIVERED','RETURNED TO CUSTOMER']))) or 0)
                achieved-=part_cost
            else: achieved=Decimal('0')
            target=Decimal(t.target_value)
            pct=(achieved/target*100) if target>0 else Decimal('0')
            out.append(TargetProgress(t.id,code,target,achieved,pct))
        return out
