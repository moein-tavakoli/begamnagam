"use client";

import { useMemo, useState, type ReactNode } from 'react';
import Link from 'next/link';
import { DataGrid, type GridColDef, type GridPaginationModel } from '@mui/x-data-grid';
import { faIR } from '@mui/x-data-grid/locales';
import Box from '@mui/material/Box';
import Button from '@mui/material/Button';
import Chip from '@mui/material/Chip';
import Typography from '@mui/material/Typography';
import VisibilityOutlined from '@mui/icons-material/VisibilityOutlined';
import { ManagementDialog } from './management-ui';
import { managementVisibleColumns, managementPageSizes, managementGridRange, managementDate, managementState, managementNumber, managementDisplayValue, managementUserHref, type ManagementRow, type ManagementRecords } from '@/lib/management';
import { walletToman } from '@/lib/wallet';

const getRowId = (row:ManagementRow) => row.record_id;
const locale = {
  ...faIR.components.MuiDataGrid.defaultProps.localeText,
  noRowsLabel:'رکوردی پیدا نشد', noResultsOverlayLabel:'نتیجه‌ای پیدا نشد',
  noColumnsOverlayLabel:'ستونی برای نمایش وجود ندارد', noColumnsOverlayManageColumns:'مدیریت ستون‌ها',
  paginationRowsPerPage:'تعداد سطر در صفحه:', paginationDisplayedRows:managementGridRange,
  paginationItemAriaLabel:(type:'first'|'last'|'previous'|'next')=>({first:'صفحهٔ اول',last:'صفحهٔ آخر',previous:'صفحهٔ قبل',next:'صفحهٔ بعد'}[type]),
};

function JsonCell({value,focused}:{value:unknown;focused:boolean}) {
  const [open,setOpen]=useState(false);
  return <><Button tabIndex={focused?0:-1} startIcon={<VisibilityOutlined/>} onClick={()=>setOpen(true)} size="small">مشاهدهٔ مقادیر</Button>{open&&<ManagementDialog title="مقادیر ثبت‌شده" onClose={()=>setOpen(false)}><Box component="pre" dir="ltr" sx={{m:0,maxHeight:'55vh',overflow:'auto',whiteSpace:'pre-wrap',overflowWrap:'anywhere',fontFamily:'inherit',fontSize:13}}>{JSON.stringify(value,null,2)}</Box></ManagementDialog>}</>;
}
function ValueCell({value,kind}:{value:unknown;kind:string}) {
  if(value===null||value===undefined||value==='') return <Typography variant="body2">—</Typography>;
  if(kind==='bool') return <Chip size="small" variant="outlined" color={value?'success':'default'} label={value?'بله':'خیر'}/>;
  if(kind==='status') return <Chip size="small" label={managementState(value)}/>;
  const text = kind==='date'?managementDate(value):kind==='money'?walletToman(String(value)):kind==='number'?managementNumber(value):String(value);
  return <Typography component="span" variant="body2" title={text} sx={{overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:'100%'}}>{text}</Typography>;
}

export function ManagementDataGrid({resource,data,rows,loading,failed,pagination,onPaginationChange,renderActions,hasActions}: {
  resource:string; data:ManagementRecords|null; rows:ManagementRow[]; loading:boolean;failed:boolean;
  pagination:GridPaginationModel; onPaginationChange:(model:GridPaginationModel)=>void;
  renderActions:(row:ManagementRow,focused:boolean)=>ReactNode; hasActions:boolean;
}) {
  const schemaKey=JSON.stringify(data?.columns||[]);
  const visibleColumns=useMemo(()=>managementVisibleColumns(JSON.parse(schemaKey) as ManagementRecords['columns']),[schemaKey]);
  const columns=useMemo<GridColDef<ManagementRow>[]>(()=>{
    const result:GridColDef<ManagementRow>[] = visibleColumns.map(col=>({
      field:col.key, headerName:col.label, sortable:false, filterable:false,
      width:col.key==='phone'?155:col.type==='date'?180:col.type==='json'?200:col.key.includes('reason')||col.key==='code'?340:155,
      minWidth:100,
      renderCell:params=>{
        if(col.type==='json')return <JsonCell value={params.value} focused={params.hasFocus}/>;
        const value=managementDisplayValue(col.key,params.value);
        const cell=<ValueCell value={value} kind={col.type}/>;
        return resource==='accounts'&&col.key==='phone'?<Button component={Link} href={managementUserHref(params.row.record_id)} tabIndex={params.hasFocus?0:-1} sx={{p:0,minWidth:0,whiteSpace:'nowrap'}}>{cell}</Button>:cell;
      },
    }));
    if(hasActions)result.unshift({field:'__actions__',headerName:'عملیات',width:82,minWidth:82,resizable:false,sortable:false,filterable:false,disableColumnMenu:true,renderCell:params=>renderActions(params.row,params.hasFocus)});
    return result;
  },[visibleColumns,resource,hasActions,renderActions]);
  return <Box sx={{width:'100%',minWidth:0,height:Math.min(640,Math.max(330,(data?.rows.length||0)*64+156))}}>
    <DataGrid<ManagementRow> aria-label={data?.title||'جدول مدیریت'} rows={rows} columns={columns} getRowId={getRowId}
      loading={loading} rowCount={data?.total??0} paginationMode="server" paginationModel={pagination}
      onPaginationModelChange={onPaginationChange} pageSizeOptions={managementPageSizes.map(value=>({value,label:value.toLocaleString('fa-IR')}))}
      disableColumnSorting disableColumnFilter disableColumnMenu disableColumnSelector disableRowSelectionOnClick rowSelection={false} hideFooterSelectedRowCount
      rowHeight={64} columnHeaderHeight={54} localeText={failed?{...locale,noRowsLabel:'اطلاعات جدول دریافت نشد؛ دوباره تلاش کنید.'}:locale}
      slotProps={{basePagination:{material:{showFirstButton:true,showLastButton:true}}}}
      sx={{bgcolor:'background.paper',fontFamily:'inherit',borderColor:'divider',borderRadius:2,
        '& .MuiDataGrid-cell':{display:'flex',alignItems:'center',minWidth:0},
        '& .MuiDataGrid-columnHeaderTitle':{fontWeight:600},
        '& .MuiDataGrid-footerContainer':{minHeight:{xs:96,sm:56},flexWrap:'wrap'},
        '& .MuiTablePagination-root':{width:'100%',overflow:'visible'},
        '& .MuiTablePagination-toolbar':{px:1,flexWrap:'wrap',justifyContent:'center',gap:.5},
        '& .MuiTablePagination-spacer':{display:'none'},
        '& .MuiTablePagination-root .MuiTablePagination-selectLabel':{display:'block',m:0,fontSize:12},
        '& .MuiTablePagination-root .MuiTablePagination-input':{display:'inline-flex',marginInline:1},
        '& .MuiTablePagination-displayedRows':{m:0,fontSize:12},
        '& .MuiTablePagination-actions':{marginInlineStart:0},
      }}/>
  </Box>;
}
