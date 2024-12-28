"use strict";(self.webpackChunkaws_amplify_gen2=self.webpackChunkaws_amplify_gen2||[]).push([[9105],{"./stories/EvaluationListAccuracyBar.stories.tsx":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.r(__webpack_exports__),__webpack_require__.d(__webpack_exports__,{Demo:()=>Demo,Focused:()=>Focused,Single:()=>Single,__namedExportsOrder:()=>__namedExportsOrder,default:()=>EvaluationListAccuracyBar_stories});var jsx_runtime=__webpack_require__("./node_modules/next/dist/compiled/react/jsx-runtime.js"),utils=(__webpack_require__("./node_modules/next/dist/compiled/react/index.js"),__webpack_require__("./lib/utils.ts"));function EvaluationListAccuracyBar({progress,accuracy,isFocused=!1}){const roundedAccuracy=Math.round(accuracy),clampedAccuracy=Math.min(Math.max(roundedAccuracy,0),100),clampedProgress=Math.min(Math.max(progress,0),100),opacity=clampedProgress/100,trueWidth=clampedAccuracy,falseWidth=100-trueWidth;return(0,jsx_runtime.jsx)("div",{className:"relative w-full h-8 bg-neutral rounded-md",children:clampedProgress>0&&(0,jsx_runtime.jsxs)(jsx_runtime.Fragment,{children:[(0,jsx_runtime.jsxs)("div",{className:(0,utils.cn)("absolute top-0 left-0 h-full flex items-center pl-2 text-sm font-medium rounded-md",isFocused?"text-focus":"text-primary-foreground"),style:{width:"auto"},children:[clampedAccuracy,"%"]}),trueWidth>0&&(0,jsx_runtime.jsxs)("div",{className:(0,utils.cn)("absolute top-0 left-0 h-full bg-true flex items-center pl-2 text-sm font-medium",isFocused?"text-focus":"text-primary-foreground"),style:{width:`${trueWidth}%`,borderTopLeftRadius:"inherit",borderBottomLeftRadius:"inherit",borderTopRightRadius:0===falseWidth?"inherit":0,borderBottomRightRadius:0===falseWidth?"inherit":0,opacity},children:[clampedAccuracy,"%"]}),falseWidth>0&&(0,jsx_runtime.jsx)("div",{className:"absolute top-0 h-full bg-false",style:{left:`${trueWidth}%`,width:`${falseWidth}%`,borderTopLeftRadius:0===trueWidth?"inherit":0,borderBottomLeftRadius:0===trueWidth?"inherit":0,borderTopRightRadius:"inherit",borderBottomRightRadius:"inherit",opacity}})]})})}EvaluationListAccuracyBar.__docgenInfo={description:"",methods:[],displayName:"EvaluationListAccuracyBar",props:{progress:{required:!0,tsType:{name:"number"},description:""},accuracy:{required:!0,tsType:{name:"number"},description:""},isFocused:{required:!1,tsType:{name:"boolean"},description:"",defaultValue:{value:"false",computed:!1}}}};const EvaluationListAccuracyBar_stories={title:"Visualization/EvaluationListAccuracyBar",component:EvaluationListAccuracyBar,parameters:{layout:"centered"},decorators:[Story=>(0,jsx_runtime.jsx)("div",{className:"w-full",children:(0,jsx_runtime.jsx)(Story,{})})]},Single={args:{progress:65,accuracy:85,isFocused:!1},decorators:[Story=>(0,jsx_runtime.jsx)("div",{className:"w-1/2 min-w-[300px]",children:(0,jsx_runtime.jsx)(Story,{})})]},Focused={args:{progress:65,accuracy:85,isFocused:!0},decorators:[Story=>(0,jsx_runtime.jsx)("div",{className:"w-1/2 min-w-[300px]",children:(0,jsx_runtime.jsx)(Story,{})})]},Demo={parameters:{layout:"padded"},decorators:[Story=>(0,jsx_runtime.jsx)("div",{className:"w-full max-w-[1200px] px-8",children:(0,jsx_runtime.jsxs)("div",{className:"grid grid-cols-2 gap-16",children:[(0,jsx_runtime.jsxs)("div",{className:"space-y-4",children:[(0,jsx_runtime.jsx)("h3",{className:"font-medium mb-2",children:"Not Focused"}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:100}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:75}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:50}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:25}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:0})]}),(0,jsx_runtime.jsxs)("div",{className:"space-y-4",children:[(0,jsx_runtime.jsx)("h3",{className:"font-medium mb-2",children:"Focused"}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:100,isFocused:!0}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:75,isFocused:!0}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:50,isFocused:!0}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:25,isFocused:!0}),(0,jsx_runtime.jsx)(EvaluationListAccuracyBar,{progress:100,accuracy:0,isFocused:!0})]})]})})]},__namedExportsOrder=["Single","Focused","Demo"];Single.parameters={...Single.parameters,docs:{...Single.parameters?.docs,source:{originalSource:'{\n  args: {\n    progress: 65,\n    accuracy: 85,\n    isFocused: false\n  },\n  decorators: [Story => <div className="w-1/2 min-w-[300px]">\n        <Story />\n      </div>]\n}',...Single.parameters?.docs?.source}}},Focused.parameters={...Focused.parameters,docs:{...Focused.parameters?.docs,source:{originalSource:'{\n  args: {\n    progress: 65,\n    accuracy: 85,\n    isFocused: true\n  },\n  decorators: [Story => <div className="w-1/2 min-w-[300px]">\n        <Story />\n      </div>]\n}',...Focused.parameters?.docs?.source}}},Demo.parameters={...Demo.parameters,docs:{...Demo.parameters?.docs,source:{originalSource:'{\n  parameters: {\n    layout: \'padded\'\n  },\n  decorators: [Story => <div className="w-full max-w-[1200px] px-8">\n        <div className="grid grid-cols-2 gap-16">\n          <div className="space-y-4">\n            <h3 className="font-medium mb-2">Not Focused</h3>\n            <EvaluationListAccuracyBar progress={100} accuracy={100} />\n            <EvaluationListAccuracyBar progress={100} accuracy={75} />\n            <EvaluationListAccuracyBar progress={100} accuracy={50} />\n            <EvaluationListAccuracyBar progress={100} accuracy={25} />\n            <EvaluationListAccuracyBar progress={100} accuracy={0} />\n          </div>\n          <div className="space-y-4">\n            <h3 className="font-medium mb-2">Focused</h3>\n            <EvaluationListAccuracyBar progress={100} accuracy={100} isFocused />\n            <EvaluationListAccuracyBar progress={100} accuracy={75} isFocused />\n            <EvaluationListAccuracyBar progress={100} accuracy={50} isFocused />\n            <EvaluationListAccuracyBar progress={100} accuracy={25} isFocused />\n            <EvaluationListAccuracyBar progress={100} accuracy={0} isFocused />\n          </div>\n        </div>\n      </div>]\n}',...Demo.parameters?.docs?.source}}}},"./lib/utils.ts":(__unused_webpack_module,__webpack_exports__,__webpack_require__)=>{__webpack_require__.d(__webpack_exports__,{cn:()=>cn});var clsx__WEBPACK_IMPORTED_MODULE_1__=__webpack_require__("./node_modules/clsx/dist/clsx.mjs"),tailwind_merge__WEBPACK_IMPORTED_MODULE_0__=__webpack_require__("./node_modules/tailwind-merge/dist/bundle-mjs.mjs");function cn(...inputs){return(0,tailwind_merge__WEBPACK_IMPORTED_MODULE_0__.QP)((0,clsx__WEBPACK_IMPORTED_MODULE_1__.$)(inputs))}}}]);