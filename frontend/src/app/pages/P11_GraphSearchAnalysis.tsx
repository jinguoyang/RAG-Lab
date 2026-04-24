import { PageHeader } from "../components/rag/PageHeader";
import { Button } from "../components/rag/Button";
import { Card, CardHeader, CardTitle, CardContent } from "../components/rag/Card";
import { Input } from "../components/rag/Input";
import { Network, ZoomIn, Info } from "lucide-react";

export function GraphSearchAnalysis() {
  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6 flex flex-col h-full overflow-hidden">
      <PageHeader
        title="图谱检索分析"
        description="查看 Neo4j 实体抽取、关系结构和子图召回情况。"
        actions={
          <Button variant="outline">
            <Network className="w-4 h-4 mr-2" /> 同步图谱状态
          </Button>
        }
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 flex-1 min-h-0">
        <div className="lg:col-span-1 space-y-4 flex flex-col">
          <Card className="shrink-0">
            <CardHeader>
              <CardTitle>测试子图抽取</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                 <label className="text-sm font-medium text-near-black">目标实体</label>
                 <Input placeholder="例如：Supplier B、Aurora" />
              </div>
              <div className="space-y-2">
                 <label className="text-sm font-medium text-near-black">最大跳数</label>
                 <select className="w-full px-3 py-2 bg-ivory border border-border-cream rounded-md text-sm">
                   <option>1（直接关系）</option>
                   <option>2（二级扩展）</option>
                   <option>3（扩展模式）</option>
                 </select>
              </div>
              <Button variant="primary" className="w-full">抽取子图</Button>
            </CardContent>
          </Card>
          
          <Card className="flex-1 overflow-auto">
            <CardHeader className="sticky top-0 bg-ivory z-10 border-b border-border-cream">
              <CardTitle>图谱状态</CardTitle>
            </CardHeader>
            <CardContent className="pt-4 space-y-4 text-sm">
               <div className="flex justify-between items-center border-b border-border-cream pb-2">
                 <span className="text-stone-gray">实体总数</span>
                 <span className="font-mono text-near-black">12,405</span>
               </div>
               <div className="flex justify-between items-center border-b border-border-cream pb-2">
                 <span className="text-stone-gray">关系总数</span>
                 <span className="font-mono text-near-black">48,192</span>
               </div>
               <div className="flex justify-between items-center border-b border-border-cream pb-2">
                 <span className="text-stone-gray">最近同步</span>
                 <span className="font-mono text-near-black">2026-04-22 01:00</span>
               </div>
               <div className="p-3 bg-info-blue/10 border border-info-blue/20 rounded text-info-blue flex items-start gap-2">
                 <Info className="w-4 h-4 mt-0.5 shrink-0" />
                 <span>图谱索引会在文档入库阶段自动执行。</span>
               </div>
            </CardContent>
          </Card>
        </div>

        <Card className="lg:col-span-2 flex flex-col overflow-hidden bg-parchment border-border-warm relative">
          <div className="absolute top-4 right-4 z-10">
            <Button variant="outline" size="sm" className="bg-ivory shadow-sm">
               <ZoomIn className="w-4 h-4 mr-2" /> 放大查看
            </Button>
          </div>
          <div className="flex-1 flex items-center justify-center relative overflow-hidden">
             {/* Mock Graph Visual */}
             <div className="relative w-full h-full p-8 flex items-center justify-center">
                <div className="absolute w-full h-full bg-[radial-gradient(#e8e6dc_1px,transparent_1px)] [background-size:16px_16px] opacity-50"></div>
                
                <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{zIndex: 0}}>
                  <line x1="40%" y1="50%" x2="60%" y2="40%" stroke="var(--border-warm)" strokeWidth="2" />
                  <line x1="40%" y1="50%" x2="55%" y2="70%" stroke="var(--border-warm)" strokeWidth="2" />
                  <line x1="60%" y1="40%" x2="75%" y2="35%" stroke="var(--terracotta)" strokeWidth="2" strokeDasharray="4" />
                </svg>

                <div className="absolute top-1/2 left-[40%] -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="bg-ivory border-2 border-near-black px-4 py-2 rounded-full shadow-md font-medium text-sm">
                    Aurora Product
                  </div>
                </div>

                <div className="absolute top-[40%] left-[60%] -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="bg-ivory border-2 border-terracotta px-4 py-2 rounded-full shadow-md font-medium text-sm">
                    Supplier B (APAC)
                  </div>
                  <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs font-mono text-terracotta bg-parchment px-1">依赖于</div>
                </div>

                <div className="absolute top-[70%] left-[55%] -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="bg-ivory border-2 border-olive-gray px-4 py-2 rounded-full shadow-md font-medium text-sm opacity-70">
                    Supplier A (US)
                  </div>
                </div>

                <div className="absolute top-[35%] left-[75%] -translate-x-1/2 -translate-y-1/2 z-10">
                  <div className="bg-error-red text-white border-2 border-error-red px-3 py-1 rounded-full shadow-md font-bold text-xs">
                    Bottleneck
                  </div>
                  <div className="absolute -bottom-6 left-1/2 -translate-x-1/2 text-xs font-mono text-stone-gray bg-parchment px-1">状态</div>
                </div>

             </div>
          </div>
          <div className="shrink-0 p-4 border-t border-border-cream bg-ivory">
             <h4 className="font-serif text-near-black mb-2">支撑 Chunk</h4>
             <ul className="space-y-2 text-sm text-stone-gray">
               <li className="flex items-center gap-2">
                 <span className="w-2 h-2 rounded-full bg-terracotta"></span>
                 <span className="font-mono text-xs">doc-9012 (chk-001)</span>
                 <span>"Supplier B in APAC is causing delays for Aurora."</span>
               </li>
             </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
