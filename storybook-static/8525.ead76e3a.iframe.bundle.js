"use strict";(self.webpackChunkaws_amplify_gen2=self.webpackChunkaws_amplify_gen2||[]).push([[8525],{"./components/BeforeAfterGauges.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{A:()=>__WEBPACK_DEFAULT_EXPORT__});var react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),_gauge__WEBPACK_IMPORTED_MODULE_2__=(__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),__webpack_require__("./components/gauge.tsx"));const BeforeAfterGauges=({title,before,after,segments,min,max,variant="grid",backgroundColor})=>{const arrowCharacter=((before,after)=>{if(void 0===before||void 0===after)return"";const difference=after-before,percentChange=difference/before*100;return 0===difference?"→":difference>0?percentChange>=50?"↑":"↗":percentChange<=-50?"↓":"↘"})(before,after);return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("div",{"data-testid":"before-after-gauges",className:"flex justify-center w-full",children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:"relative",children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)(_gauge__WEBPACK_IMPORTED_MODULE_2__._,{value:after,beforeValue:before,title,segments,min,max,showTicks:"detail"===variant,backgroundColor}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:"absolute left-1/2 -translate-x-1/2 text-xs text-muted-foreground whitespace-nowrap",style:{bottom:"detail"===variant?"max(-30px, calc(-32px + 18%))":"max(-30px, calc(-38px + 24%))"},children:[void 0!==before?`${before}%`:"",arrowCharacter,void 0!==after?`${after}%`:""]})]})})},__WEBPACK_DEFAULT_EXPORT__=BeforeAfterGauges;BeforeAfterGauges.__docgenInfo={description:"",methods:[],displayName:"BeforeAfterGauges",props:{title:{required:!0,tsType:{name:"string"},description:""},before:{required:!1,tsType:{name:"number"},description:""},after:{required:!1,tsType:{name:"number"},description:""},segments:{required:!1,tsType:{name:"Array",elements:[{name:"Segment"}],raw:"Segment[]"},description:""},min:{required:!1,tsType:{name:"number"},description:""},max:{required:!1,tsType:{name:"number"},description:""},variant:{required:!1,tsType:{name:"union",raw:"'grid' | 'detail'",elements:[{name:"literal",value:"'grid'"},{name:"literal",value:"'detail'"}]},description:"",defaultValue:{value:"'grid'",computed:!1}},backgroundColor:{required:!1,tsType:{name:"string"},description:""}}}},"./components/gauge.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{_:()=>Gauge});var react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),react__WEBPACK_IMPORTED_MODULE_1__=__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),_lib_utils__WEBPACK_IMPORTED_MODULE_2__=__webpack_require__("./lib/utils.ts");const calculateAngle=percent=>percent/100*(7*Math.PI/6),GaugeComponent=({value,beforeValue,segments,min=0,max=100,title,backgroundColor="var(--card)",showTicks=!0,information,informationUrl,priority=!1})=>{const[animatedValue,setAnimatedValue]=(0,react__WEBPACK_IMPORTED_MODULE_1__.useState)(0),[animatedBeforeValue,setAnimatedBeforeValue]=(0,react__WEBPACK_IMPORTED_MODULE_1__.useState)(0),normalizedValue=void 0!==value?(value-min)/(max-min)*100:0,[showInfo,setShowInfo]=(0,react__WEBPACK_IMPORTED_MODULE_1__.useState)(!1);(0,react__WEBPACK_IMPORTED_MODULE_1__.useEffect)((()=>{const startTime=performance.now(),startAngle=animatedValue,targetAngle=normalizedValue,startBeforeAngle=animatedBeforeValue,targetBeforeAngle=void 0!==beforeValue?(beforeValue-min)/(max-min)*100:null,animate=currentTime=>{const elapsed=currentTime-startTime,progress=Math.min(elapsed/600,1),easeProgress=1-Math.pow(1-progress,3),currentBeforeValue=null!==startBeforeAngle&&null!==targetBeforeAngle?startBeforeAngle+(targetBeforeAngle-startBeforeAngle)*easeProgress:null;setAnimatedValue(startAngle+(targetAngle-startAngle)*easeProgress),setAnimatedBeforeValue(null!=currentBeforeValue?currentBeforeValue:0),progress<1&&requestAnimationFrame(animate)};requestAnimationFrame(animate)}),[normalizedValue,beforeValue]);const calculateCoordinates=(angle,r=80)=>({x:r*Math.cos(angle-Math.PI/2),y:r*Math.sin(angle-Math.PI/2)}),topPadding=showTicks?104:80,viewBoxHeight=showTicks?200:170,clipHeight=showTicks?168:144;return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("div",{className:"flex flex-col items-center w-full h-full max-h-[220px]",children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:"relative w-full h-full",style:{maxWidth:"20em"},children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:"relative w-full h-full",children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("svg",{viewBox:`-120 -${topPadding} 240 ${viewBoxHeight}`,preserveAspectRatio:"xMidYMid meet",style:{width:"100%",height:"100%",maxHeight:"100%"},children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("defs",{children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("clipPath",{id:"gaugeClip",children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("rect",{x:"-120",y:-topPadding,width:"240",height:clipHeight})})}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("g",{clipPath:"url(#gaugeClip)",children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("circle",{cx:"0",cy:"0",r:80,fill:backgroundColor}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("g",{transform:"rotate(-105)",children:[null==segments?void 0:segments.map(((segment,index)=>{if(segment.end-segment.start<=50){const startAngle=calculateAngle(segment.start),endAngle=calculateAngle(segment.end),outerStart=calculateCoordinates(startAngle),outerEnd=calculateCoordinates(endAngle),innerStart=calculateCoordinates(startAngle,55),innerEnd=calculateCoordinates(endAngle,55);return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:`M ${outerStart.x} ${outerStart.y} \n               A 80 80 0 0 1 ${outerEnd.x} ${outerEnd.y}\n               L ${innerEnd.x} ${innerEnd.y} \n               A 55 55 0 0 0 ${innerStart.x} ${innerStart.y} \n               Z`,fill:segment.color,stroke:"none"},index)}const midPoint=segment.start+50,startAngle1=calculateAngle(segment.start),endAngle1=calculateAngle(midPoint),startAngle2=calculateAngle(midPoint),endAngle2=calculateAngle(segment.end),outerStart1=calculateCoordinates(startAngle1),outerEnd1=calculateCoordinates(endAngle1),innerStart1=calculateCoordinates(startAngle1,55),innerEnd1=calculateCoordinates(endAngle1,55),outerStart2=calculateCoordinates(startAngle2),outerEnd2=calculateCoordinates(endAngle2),innerStart2=calculateCoordinates(startAngle2,55),innerEnd2=calculateCoordinates(endAngle2,55);return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("g",{children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:`M ${outerStart1.x} ${outerStart1.y} \n               A 80 80 0 0 1 ${outerEnd1.x} ${outerEnd1.y}\n               L ${innerEnd1.x} ${innerEnd1.y} \n               A 55 55 0 0 0 ${innerStart1.x} ${innerStart1.y} \n               Z`,fill:segment.color,stroke:"none"}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:`M ${outerStart2.x} ${outerStart2.y} \n               A 80 80 0 0 1 ${outerEnd2.x} ${outerEnd2.y}\n               L ${innerEnd2.x} ${innerEnd2.y} \n               A 55 55 0 0 0 ${innerStart2.x} ${innerStart2.y} \n               Z`,fill:segment.color,stroke:"none"})]},index)})),showTicks&&[...segments||[],{start:100,end:100,color:"transparent"}].map(((segment,index)=>{const angle=calculateAngle(segment.start),{x,y}=calculateCoordinates(angle),lineEndX=1.08*x,lineEndY=1.08*y,angleInDegrees=180*angle/Math.PI,textOffset=105-10*(Math.abs(angleInDegrees-90)<15?.95:.3*Math.pow(Math.abs(angleInDegrees-90)/90,.5))+(100===segment.start?3:0),textX=textOffset*Math.cos(angle-Math.PI/2),textY=textOffset*Math.sin(angle-Math.PI/2);return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("g",{children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("line",{x1:x,y1:y,x2:lineEndX,y2:lineEndY,className:"stroke-muted-foreground",strokeWidth:"0.5"}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("g",{transform:`translate(${textX} ${textY}) rotate(105)`,children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("text",{x:"0",y:"0",textAnchor:"middle",dominantBaseline:"middle",fontSize:"12",className:"fill-muted-foreground",children:[segment.start,"%"]})})]},index)})),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("g",{children:[void 0!==beforeValue&&(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:"M 0,-80 L -6,0 L 6,0 Z",className:"fill-muted-foreground opacity-40",transform:`rotate(${210*animatedBeforeValue/100})`}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:"M 0,-80 L -6,0 L 6,0 Z",className:(0,_lib_utils__WEBPACK_IMPORTED_MODULE_2__.cn)(priority?"fill-focus":"fill-foreground",void 0===value&&"fill-card"),transform:`rotate(${210*animatedValue/100})`}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("circle",{cx:"0",cy:"0",r:"10",className:priority?"fill-focus":"fill-foreground"})]})]}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("text",{x:"0",y:45,textAnchor:"middle",className:(0,_lib_utils__WEBPACK_IMPORTED_MODULE_2__.cn)("text-[2.25rem] font-bold",priority?"fill-focus":"fill-foreground"),dominantBaseline:"middle",children:void 0!==value?value%1==0?`${value}%`:`${value.toFixed(1)}%`:""})]})]}),title&&(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:(0,_lib_utils__WEBPACK_IMPORTED_MODULE_2__.cn)("absolute left-1/2 -translate-x-1/2 flex items-center gap-2 whitespace-nowrap","text-[clamp(0.75rem,4vw,1rem)]",priority?"text-focus":"text-foreground"),style:{bottom:showTicks?"5%":"2%"},children:[title,information&&(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("button",{onClick:()=>setShowInfo(!showInfo),className:"text-muted-foreground hover:text-foreground","aria-label":"Toggle information",children:(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("svg",{width:"16",height:"16",viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:"2",children:[(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("circle",{cx:"12",cy:"12",r:"10"}),(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("path",{d:"M12 16v-4M12 8h.01"})]})})]})]}),showInfo&&information&&(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsxs)("div",{className:"w-full text-sm text-left -mt-6 mb-8 pl-4 text-muted-foreground overflow-y-auto max-h-[100px]",children:[information.split("\n\n").map(((paragraph,index)=>(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("p",{className:index>0?"mt-4":"",children:paragraph},index))),informationUrl&&(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("a",{href:informationUrl,target:"_blank",rel:"noopener noreferrer",className:"text-primary hover:underline mt-1 block",children:"more..."})]})]})})},defaultSegments=[{start:0,end:60,color:"var(--gauge-inviable)"},{start:60,end:80,color:"var(--gauge-converging)"},{start:80,end:90,color:"var(--gauge-almost)"},{start:90,end:95,color:"var(--gauge-viable)"},{start:95,end:100,color:"var(--gauge-great)"}],Gauge=({segments=defaultSegments,...props})=>(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)(GaugeComponent,{segments,...props});Gauge.__docgenInfo={description:"",methods:[],displayName:"Gauge",props:{value:{required:!1,tsType:{name:"number"},description:""},beforeValue:{required:!1,tsType:{name:"number"},description:""},segments:{required:!1,tsType:{name:"Array",elements:[{name:"Segment"}],raw:"Segment[]"},description:"",defaultValue:{value:"[\n  { start: 0, end: 60, color: 'var(--gauge-inviable)' },\n  { start: 60, end: 80, color: 'var(--gauge-converging)' },\n  { start: 80, end: 90, color: 'var(--gauge-almost)' },\n  { start: 90, end: 95, color: 'var(--gauge-viable)' },\n  { start: 95, end: 100, color: 'var(--gauge-great)' },\n]",computed:!1}},min:{required:!1,tsType:{name:"number"},description:""},max:{required:!1,tsType:{name:"number"},description:""},title:{required:!1,tsType:{name:"ReactReactNode",raw:"React.ReactNode"},description:""},backgroundColor:{required:!1,tsType:{name:"string"},description:""},showTicks:{required:!1,tsType:{name:"boolean"},description:""},information:{required:!1,tsType:{name:"string"},description:""},informationUrl:{required:!1,tsType:{name:"string"},description:""},priority:{required:!1,tsType:{name:"boolean"},description:""}}}}}]);