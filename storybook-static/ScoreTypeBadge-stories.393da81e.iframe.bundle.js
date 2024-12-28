/*! For license information please see ScoreTypeBadge-stories.393da81e.iframe.bundle.js.LICENSE.txt */
"use strict";(self.webpackChunkaws_amplify_gen2=self.webpackChunkaws_amplify_gen2||[]).push([[1312],{"./stories/ScoreTypeBadge.stories.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.r(__webpack_exports__),__webpack_require__.d(__webpack_exports__,{DataBalance:()=>DataBalance,ScoreGoals:()=>ScoreGoals,ScoreTypes:()=>ScoreTypes,__namedExportsOrder:()=>__namedExportsOrder,default:()=>ScoreTypeBadge_stories});var jsx_runtime=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),badge=(__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),__webpack_require__("./components/ui/badge.tsx"));function ScoreTypeBadge({icon:Icon,label,subLabel,color}){return(0,jsx_runtime.jsxs)("div",{className:"flex flex-col justify-between h-full p-3 rounded-md",style:{backgroundColor:`hsl(var(--${color}-3))`},children:[(0,jsx_runtime.jsxs)("div",{className:"flex items-center gap-2",children:[(0,jsx_runtime.jsx)(Icon,{className:"h-6 w-6 shrink-0",style:{color:`hsl(var(--${color}-11))`}}),(0,jsx_runtime.jsx)("span",{className:"text-sm font-medium text-foreground",children:label})]}),(0,jsx_runtime.jsx)("div",{className:"mt-2",children:(0,jsx_runtime.jsx)(badge.E,{variant:"secondary",children:subLabel})})]})}ScoreTypeBadge.__docgenInfo={description:"",methods:[],displayName:"ScoreTypeBadge",props:{icon:{required:!0,tsType:{name:"LucideIcon"},description:""},label:{required:!0,tsType:{name:"string"},description:""},subLabel:{required:!0,tsType:{name:"string"},description:""},color:{required:!0,tsType:{name:"string"},description:""}}};var createLucideIcon=__webpack_require__("./node_modules/lucide-react/dist/esm/createLucideIcon.js");const SquareSplitVertical=(0,createLucideIcon.A)("SquareSplitVertical",[["path",{d:"M5 8V5c0-1 1-2 2-2h10c1 0 2 1 2 2v3",key:"1pi83i"}],["path",{d:"M19 16v3c0 1-1 2-2 2H7c-1 0-2-1-2-2v-3",key:"ido5k7"}],["line",{x1:"4",x2:"20",y1:"12",y2:"12",key:"1e0a9i"}]]);var icons_layers=__webpack_require__("./node_modules/lucide-react/dist/esm/icons/layers.js"),scale=__webpack_require__("./node_modules/lucide-react/dist/esm/icons/scale.js"),equal_not=__webpack_require__("./node_modules/lucide-react/dist/esm/icons/equal-not.js");const Target=(0,createLucideIcon.A)("Target",[["circle",{cx:"12",cy:"12",r:"10",key:"1mglay"}],["circle",{cx:"12",cy:"12",r:"6",key:"1vlfrh"}],["circle",{cx:"12",cy:"12",r:"2",key:"1c9p78"}]]),ShieldAlert=(0,createLucideIcon.A)("ShieldAlert",[["path",{d:"M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z",key:"oel41y"}],["path",{d:"M12 8v4",key:"1got3b"}],["path",{d:"M12 16h.01",key:"1drbdi"}]]),ScoreTypeBadge_stories={title:"Components/ScoreTypeBadge",component:ScoreTypeBadge,decorators:[Story=>(0,jsx_runtime.jsx)("div",{className:"bg-background p-4",children:(0,jsx_runtime.jsx)(Story,{})})]},ScoreTypes=()=>(0,jsx_runtime.jsxs)("div",{className:"space-y-4",children:[(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:SquareSplitVertical,label:"Binary",subLabel:"2 classes",color:"blue"}),(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:icons_layers.A,label:"Multi-class",subLabel:"3+ classes",color:"purple"})]}),DataBalance=()=>(0,jsx_runtime.jsxs)("div",{className:"space-y-4",children:[(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:scale.A,label:"Balanced",subLabel:"Equal distribution",color:"green"}),(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:equal_not.A,label:"Unbalanced",subLabel:"Skewed distribution",color:"yellow"})]}),ScoreGoals=()=>(0,jsx_runtime.jsxs)("div",{className:"space-y-4",children:[(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:Target,label:"Detect All Positives",subLabel:"High recall",color:"indigo"}),(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:ShieldAlert,label:"Avoid False Positives",subLabel:"High precision",color:"red"}),(0,jsx_runtime.jsx)(ScoreTypeBadge,{icon:scale.A,label:"Balanced Approach",subLabel:"High F1-score",color:"orange"})]}),__namedExportsOrder=["ScoreTypes","DataBalance","ScoreGoals"];ScoreTypes.parameters={...ScoreTypes.parameters,docs:{...ScoreTypes.parameters?.docs,source:{originalSource:'() => <div className="space-y-4">\n    <ScoreTypeBadge icon={SquareSplitVertical} label="Binary" subLabel="2 classes" color="blue" />\n    <ScoreTypeBadge icon={Layers} label="Multi-class" subLabel="3+ classes" color="purple" />\n  </div>',...ScoreTypes.parameters?.docs?.source}}},DataBalance.parameters={...DataBalance.parameters,docs:{...DataBalance.parameters?.docs,source:{originalSource:'() => <div className="space-y-4">\n    <ScoreTypeBadge icon={Scale} label="Balanced" subLabel="Equal distribution" color="green" />\n    <ScoreTypeBadge icon={EqualNot} label="Unbalanced" subLabel="Skewed distribution" color="yellow" />\n  </div>',...DataBalance.parameters?.docs?.source}}},ScoreGoals.parameters={...ScoreGoals.parameters,docs:{...ScoreGoals.parameters?.docs,source:{originalSource:'() => <div className="space-y-4">\n    <ScoreTypeBadge icon={Target} label="Detect All Positives" subLabel="High recall" color="indigo" />\n    <ScoreTypeBadge icon={ShieldAlert} label="Avoid False Positives" subLabel="High precision" color="red" />\n    <ScoreTypeBadge icon={Scale} label="Balanced Approach" subLabel="High F1-score" color="orange" />\n  </div>',...ScoreGoals.parameters?.docs?.source}}}},"./components/ui/badge.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{E:()=>Badge});var react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),class_variance_authority__WEBPACK_IMPORTED_MODULE_2__=(__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),__webpack_require__("./node_modules/class-variance-authority/dist/index.mjs")),_lib_utils__WEBPACK_IMPORTED_MODULE_3__=__webpack_require__("./lib/utils.ts");const badgeVariants=(0,class_variance_authority__WEBPACK_IMPORTED_MODULE_2__.F)("inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",{variants:{variant:{default:"border-transparent bg-primary text-primary-foreground hover:bg-primary/80",secondary:"border-transparent bg-secondary text-secondary-foreground hover:bg-secondary/80",destructive:"border-transparent bg-destructive text-destructive-foreground hover:bg-destructive/80",outline:"text-foreground",success:"border-transparent bg-success text-success-foreground hover:bg-success/80"}},defaultVariants:{variant:"default"}});function Badge({className,variant,...props}){return(0,react_jsx_runtime__WEBPACK_IMPORTED_MODULE_0__.jsx)("div",{className:(0,_lib_utils__WEBPACK_IMPORTED_MODULE_3__.cn)(badgeVariants({variant}),className),...props})}Badge.__docgenInfo={description:"",methods:[],displayName:"Badge",composes:["VariantProps"]}},"./lib/utils.ts":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{cn:()=>cn});var clsx__WEBPACK_IMPORTED_MODULE_1__=__webpack_require__("./node_modules/clsx/dist/clsx.mjs"),tailwind_merge__WEBPACK_IMPORTED_MODULE_0__=__webpack_require__("./node_modules/tailwind-merge/dist/bundle-mjs.mjs");function cn(...inputs){return(0,tailwind_merge__WEBPACK_IMPORTED_MODULE_0__.QP)((0,clsx__WEBPACK_IMPORTED_MODULE_1__.$)(inputs))}},"./node_modules/class-variance-authority/dist/index.mjs":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{function r(e){var t,f,n="";if("string"==typeof e||"number"==typeof e)n+=e;else if("object"==typeof e)if(Array.isArray(e))for(t=0;t<e.length;t++)e[t]&&(f=r(e[t]))&&(n&&(n+=" "),n+=f);else for(t in e)e[t]&&(n&&(n+=" "),n+=t);return n}function clsx(){for(var e,t,f=0,n="";f<arguments.length;)(e=arguments[f++])&&(t=r(e))&&(n&&(n+=" "),n+=t);return n}__webpack_require__.d(__webpack_exports__,{F:()=>cva});const falsyToString=value=>"boolean"==typeof value?"".concat(value):0===value?"0":value,cx=clsx,cva=(base,config)=>props=>{var ref;if(null==(null==config?void 0:config.variants))return cx(base,null==props?void 0:props.class,null==props?void 0:props.className);const{variants,defaultVariants}=config,getVariantClassNames=Object.keys(variants).map((variant=>{const variantProp=null==props?void 0:props[variant],defaultVariantProp=null==defaultVariants?void 0:defaultVariants[variant];if(null===variantProp)return null;const variantKey=falsyToString(variantProp)||falsyToString(defaultVariantProp);return variants[variant][variantKey]})),propsWithoutUndefined=props&&Object.entries(props).reduce(((acc,param)=>{let[key,value]=param;return void 0===value||(acc[key]=value),acc}),{}),getCompoundVariantClassNames=null==config||null===(ref=config.compoundVariants)||void 0===ref?void 0:ref.reduce(((acc,param1)=>{let{class:cvClass,className:cvClassName,...compoundVariantOptions}=param1;return Object.entries(compoundVariantOptions).every((param=>{let[key,value]=param;return Array.isArray(value)?value.includes({...defaultVariants,...propsWithoutUndefined}[key]):{...defaultVariants,...propsWithoutUndefined}[key]===value}))?[...acc,cvClass,cvClassName]:acc}),[]);return cx(base,getVariantClassNames,getCompoundVariantClassNames,null==props?void 0:props.class,null==props?void 0:props.className)}},"./node_modules/lucide-react/dist/esm/createLucideIcon.js":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{A:()=>createLucideIcon});var react=__webpack_require__("./node_modules/next/dist/compiled/react/index.js");const mergeClasses=(...classes)=>classes.filter(((className,index,array)=>Boolean(className)&&array.indexOf(className)===index)).join(" ");var defaultAttributes={xmlns:"http://www.w3.org/2000/svg",width:24,height:24,viewBox:"0 0 24 24",fill:"none",stroke:"currentColor",strokeWidth:2,strokeLinecap:"round",strokeLinejoin:"round"};const Icon=(0,react.forwardRef)((({color="currentColor",size=24,strokeWidth=2,absoluteStrokeWidth,className="",children,iconNode,...rest},ref)=>(0,react.createElement)("svg",{ref,...defaultAttributes,width:size,height:size,stroke:color,strokeWidth:absoluteStrokeWidth?24*Number(strokeWidth)/Number(size):strokeWidth,className:mergeClasses("lucide",className),...rest},[...iconNode.map((([tag,attrs])=>(0,react.createElement)(tag,attrs))),...Array.isArray(children)?children:[children]]))),createLucideIcon=(iconName,iconNode)=>{const Component=(0,react.forwardRef)((({className,...props},ref)=>{return(0,react.createElement)(Icon,{ref,iconNode,className:mergeClasses(`lucide-${string=iconName,string.replace(/([a-z0-9])([A-Z])/g,"$1-$2").toLowerCase()}`,className),...props});var string}));return Component.displayName=`${iconName}`,Component}},"./node_modules/lucide-react/dist/esm/icons/equal-not.js":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{A:()=>EqualNot});const EqualNot=(0,__webpack_require__("./node_modules/lucide-react/dist/esm/createLucideIcon.js").A)("EqualNot",[["line",{x1:"5",x2:"19",y1:"9",y2:"9",key:"1nwqeh"}],["line",{x1:"5",x2:"19",y1:"15",y2:"15",key:"g8yjpy"}],["line",{x1:"19",x2:"5",y1:"5",y2:"19",key:"1x9vlm"}]])},"./node_modules/lucide-react/dist/esm/icons/layers.js":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{A:()=>Layers});const Layers=(0,__webpack_require__("./node_modules/lucide-react/dist/esm/createLucideIcon.js").A)("Layers",[["path",{d:"m12.83 2.18a2 2 0 0 0-1.66 0L2.6 6.08a1 1 0 0 0 0 1.83l8.58 3.91a2 2 0 0 0 1.66 0l8.58-3.9a1 1 0 0 0 0-1.83Z",key:"8b97xw"}],["path",{d:"m22 17.65-9.17 4.16a2 2 0 0 1-1.66 0L2 17.65",key:"dd6zsq"}],["path",{d:"m22 12.65-9.17 4.16a2 2 0 0 1-1.66 0L2 12.65",key:"ep9fru"}]])},"./node_modules/lucide-react/dist/esm/icons/scale.js":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{A:()=>Scale});const Scale=(0,__webpack_require__("./node_modules/lucide-react/dist/esm/createLucideIcon.js").A)("Scale",[["path",{d:"m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z",key:"7g6ntu"}],["path",{d:"m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z",key:"ijws7r"}],["path",{d:"M7 21h10",key:"1b0cd5"}],["path",{d:"M12 3v18",key:"108xh3"}],["path",{d:"M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2",key:"3gwbw2"}]])}}]);