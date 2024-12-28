/*! For license information please see 3577.23f0499b.iframe.bundle.js.LICENSE.txt */
"use strict";(self.webpackChunkaws_amplify_gen2=self.webpackChunkaws_amplify_gen2||[]).push([[3577],{"./components/confusion-matrix.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{M:()=>ConfusionMatrix});var jsx_runtime=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),react=__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),dist=__webpack_require__("./node_modules/class-variance-authority/dist/index.mjs"),utils=__webpack_require__("./lib/utils.ts");const alertVariants=(0,dist.F)("relative w-full rounded-lg border px-4 py-3 text-sm [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg]:text-foreground [&>svg~*]:pl-7",{variants:{variant:{default:"bg-background text-foreground",destructive:"border-destructive/50 text-destructive dark:border-destructive [&>svg]:text-destructive"}},defaultVariants:{variant:"default"}}),Alert=react.forwardRef((({className,variant,...props},ref)=>(0,jsx_runtime.jsx)("div",{ref,role:"alert",className:(0,utils.cn)(alertVariants({variant}),className),...props})));Alert.displayName="Alert";const AlertTitle=react.forwardRef((({className,...props},ref)=>(0,jsx_runtime.jsx)("h5",{ref,className:(0,utils.cn)("mb-1 font-medium leading-none tracking-tight",className),...props})));AlertTitle.displayName="AlertTitle";const AlertDescription=react.forwardRef((({className,...props},ref)=>(0,jsx_runtime.jsx)("div",{ref,className:(0,utils.cn)("text-sm [&_p]:leading-relaxed",className),...props})));AlertDescription.displayName="AlertDescription",Alert.__docgenInfo={description:"",methods:[],displayName:"Alert"},AlertTitle.__docgenInfo={description:"",methods:[],displayName:"AlertTitle"},AlertDescription.__docgenInfo={description:"",methods:[],displayName:"AlertDescription"};var react_icons_esm=__webpack_require__("./node_modules/@radix-ui/react-icons/dist/react-icons.esm.js");const Grid2x2=(0,__webpack_require__("./node_modules/lucide-react/dist/esm/createLucideIcon.js").A)("Grid2x2",[["rect",{width:"18",height:"18",x:"3",y:"3",rx:"2",key:"afitv7"}],["path",{d:"M3 12h18",key:"1i2n21"}],["path",{d:"M12 3v18",key:"108xh3"}]]);var arrow_right=__webpack_require__("./node_modules/lucide-react/dist/esm/icons/arrow-right.js"),tooltip=__webpack_require__("./components/ui/tooltip.tsx");function ConfusionMatrix({data,onSelectionChange}){if(!data||data.matrix.length!==data.labels.length)return(0,jsx_runtime.jsxs)(Alert,{variant:"destructive",children:[(0,jsx_runtime.jsx)(react_icons_esm.Pip,{className:"h-4 w-4"}),(0,jsx_runtime.jsx)(AlertTitle,{children:"Error"}),(0,jsx_runtime.jsx)(AlertDescription,{children:"Invalid confusion matrix data"})]});const maxValue=Math.max(...data.matrix.flat()),getBackgroundColor=value=>{const intensity=Math.round(value/maxValue*10);return`hsl(var(--violet-${Math.max(3,intensity)}))`},handleCellClick=(predicted,actual)=>{null==onSelectionChange||onSelectionChange({predicted,actual})},handlePredictedLabelClick=label=>{null==onSelectionChange||onSelectionChange({predicted:label,actual:null})},handleActualLabelClick=label=>{null==onSelectionChange||onSelectionChange({predicted:null,actual:label})};return(0,jsx_runtime.jsxs)("div",{className:"flex flex-col w-full gap-1",children:[(0,jsx_runtime.jsxs)("div",{className:"flex items-center gap-1 text-sm text-foreground h-5",children:[(0,jsx_runtime.jsx)(Grid2x2,{className:"w-4 h-4 text-foreground shrink-0"}),(0,jsx_runtime.jsx)("span",{children:"Confusion matrix"})]}),(0,jsx_runtime.jsxs)("div",{className:"flex",children:[(0,jsx_runtime.jsxs)("div",{className:"flex",children:[(0,jsx_runtime.jsx)("div",{className:"w-6",children:(0,jsx_runtime.jsx)("div",{className:"flex flex-col items-center justify-center w-6",style:{height:64*data.labels.length+"px"},children:(0,jsx_runtime.jsx)("span",{className:"-rotate-90 whitespace-nowrap text-sm  text-muted-foreground truncate",children:"Actual"})})}),(0,jsx_runtime.jsx)("div",{className:"flex flex-col w-6 shrink-0",children:data.labels.map(((label,index)=>(0,jsx_runtime.jsx)(tooltip.Bc,{children:(0,jsx_runtime.jsxs)(tooltip.m_,{children:[(0,jsx_runtime.jsx)(tooltip.k$,{asChild:!0,children:(0,jsx_runtime.jsx)("div",{onClick:()=>handleActualLabelClick(label),className:"flex items-center justify-center h-16 relative min-w-0 cursor-pointer hover:bg-muted/50",children:(0,jsx_runtime.jsx)("span",{className:"-rotate-90 whitespace-nowrap text-sm  text-muted-foreground truncate",children:label})})}),(0,jsx_runtime.jsx)(tooltip.ZI,{children:(0,jsx_runtime.jsxs)("div",{className:"flex flex-col gap-1",children:[(0,jsx_runtime.jsx)("p",{children:label}),(0,jsx_runtime.jsxs)("div",{role:"button",onClick:()=>handleActualLabelClick(label),className:"flex items-center gap-1 text-xs bg-muted  px-2 py-0.5 rounded-full mt-1 text-muted-foreground  cursor-pointer hover:bg-muted/80",children:[(0,jsx_runtime.jsx)("span",{children:"View"}),(0,jsx_runtime.jsx)(arrow_right.A,{className:"h-3 w-3"})]})]})})]})},`row-${index}`)))})]}),(0,jsx_runtime.jsx)("div",{className:"flex flex-col min-w-0 flex-1",children:(0,jsx_runtime.jsxs)("div",{className:"flex flex-col",children:[(0,jsx_runtime.jsx)("div",{className:"flex",children:data.matrix[0].map(((_,colIndex)=>(0,jsx_runtime.jsx)("div",{className:"flex flex-col flex-1 basis-0 min-w-0",children:data.matrix.map(((row,rowIndex)=>{return(0,jsx_runtime.jsx)(tooltip.Bc,{children:(0,jsx_runtime.jsxs)(tooltip.m_,{children:[(0,jsx_runtime.jsx)(tooltip.k$,{asChild:!0,children:(0,jsx_runtime.jsx)("div",{onClick:()=>handleCellClick(data.labels[colIndex],data.labels[rowIndex]),className:`flex items-center justify-center h-16\n                              text-sm font-medium truncate ${value=row[colIndex],Math.round(value/maxValue*10)>5?"text-white dark:text-foreground":"text-primary"}\n                              cursor-pointer hover:opacity-80`,style:{backgroundColor:getBackgroundColor(row[colIndex])},children:row[colIndex]})}),(0,jsx_runtime.jsx)(tooltip.ZI,{children:(0,jsx_runtime.jsxs)("div",{className:"flex flex-col gap-1",children:[(0,jsx_runtime.jsxs)("p",{children:["Predicted: ",data.labels[colIndex]]}),(0,jsx_runtime.jsxs)("p",{children:["Actual: ",data.labels[rowIndex]]}),(0,jsx_runtime.jsxs)("p",{children:["Count: ",row[colIndex]]}),(0,jsx_runtime.jsxs)("div",{role:"button",onClick:()=>handleCellClick(data.labels[colIndex],data.labels[rowIndex]),className:"flex items-center gap-1 text-xs bg-muted  px-2 py-0.5 rounded-full mt-1 text-muted-foreground  cursor-pointer hover:bg-muted/80",children:[(0,jsx_runtime.jsx)("span",{children:"View"}),(0,jsx_runtime.jsx)(arrow_right.A,{className:"h-3 w-3"})]})]})})]})},`cell-${rowIndex}-${colIndex}`);var value}))},`col-${colIndex}`)))}),(0,jsx_runtime.jsx)("div",{className:"flex",children:data.labels.map(((label,index)=>(0,jsx_runtime.jsx)(tooltip.Bc,{children:(0,jsx_runtime.jsxs)(tooltip.m_,{children:[(0,jsx_runtime.jsx)(tooltip.k$,{asChild:!0,children:(0,jsx_runtime.jsx)("div",{onClick:()=>handlePredictedLabelClick(label),className:"flex-1 basis-0 flex items-center justify-center  border-t-0 min-w-0 w-8 overflow-hidden cursor-pointer hover:bg-muted/50",children:(0,jsx_runtime.jsx)("span",{className:"text-sm text-muted-foreground truncate w-full  text-center",children:label})})}),(0,jsx_runtime.jsx)(tooltip.ZI,{children:(0,jsx_runtime.jsxs)("div",{className:"flex flex-col gap-1",children:[(0,jsx_runtime.jsx)("p",{children:label}),(0,jsx_runtime.jsxs)("div",{role:"button",onClick:()=>handlePredictedLabelClick(label),className:"flex items-center gap-1 text-xs bg-muted  px-2 py-0.5 rounded-full mt-1 text-muted-foreground  cursor-pointer hover:bg-muted/80",children:[(0,jsx_runtime.jsx)("span",{children:"View"}),(0,jsx_runtime.jsx)(arrow_right.A,{className:"h-3 w-3"})]})]})})]})},`bottom-${index}`)))}),(0,jsx_runtime.jsx)("div",{className:"flex",children:(0,jsx_runtime.jsx)("div",{className:"flex-1 basis-0 flex items-center justify-center  border-t-0 min-w-0 overflow-hidden",children:(0,jsx_runtime.jsx)("span",{className:"text-sm text-muted-foreground truncate",children:"Predicted"})})})]})})]})]})}ConfusionMatrix.__docgenInfo={description:'ConfusionMatrix Component\n\nDisplays a confusion matrix with interactive elements:\n- Clickable cells showing the count of predictions\n- Tooltips with detailed information\n- Row labels showing actual classes\n- Column labels showing predicted classes\n\nAll interactions (cell clicks, row labels, column labels) emit a standardized\nselection event with both predicted and actual values, using null for the \nunselected dimension:\n- Cell click: { predicted: "class1", actual: "class2" }\n- Row label: { predicted: null, actual: "class2" }\n- Column label: { predicted: "class1", actual: null }',methods:[],displayName:"ConfusionMatrix",props:{data:{required:!0,tsType:{name:"ConfusionMatrixData"},description:""},onSelectionChange:{required:!1,tsType:{name:"signature",type:"function",raw:"(selection: {\n  predicted: string | null\n  actual: string | null\n}) => void",signature:{arguments:[{type:{name:"signature",type:"object",raw:"{\n  predicted: string | null\n  actual: string | null\n}",signature:{properties:[{key:"predicted",value:{name:"union",raw:"string | null",elements:[{name:"string"},{name:"null"}],required:!0}},{key:"actual",value:{name:"union",raw:"string | null",elements:[{name:"string"},{name:"null"}],required:!0}}]}},name:"selection"}],return:{name:"void"}}},description:""}}}}}]);