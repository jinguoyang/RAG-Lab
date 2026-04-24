import { useState } from "react";
import { useNavigate } from "react-router";
import { Button } from "../components/rag/Button";
import { Input } from "../components/rag/Input";
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "../components/rag/Card";
import { Alert } from "../components/rag/Alert";

export function Login() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setError("");
    
    // Simulate login
    setTimeout(() => {
      setIsLoading(false);
      navigate("/");
    }, 1000);
  };

  return (
    <div className="min-h-screen bg-parchment flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-4xl font-serif text-terracotta mb-2">RAG 平台</h1>
          <p className="text-stone-gray">企业知识库与调试系统</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>登录</CardTitle>
          </CardHeader>
          <form onSubmit={handleLogin}>
            <CardContent className="space-y-4">
              {error && (
                <Alert variant="error" title="认证失败">
                  {error}
                </Alert>
              )}
              <Input 
                label="用户名或邮箱" 
                placeholder="admin@example.com"
                required
              />
              <Input 
                label="密码" 
                type="password"
                placeholder="••••••••"
                required
              />
            </CardContent>
            <CardFooter>
              <Button 
                type="submit" 
                variant="primary" 
                className="w-full"
                disabled={isLoading}
              >
                {isLoading ? "登录中..." : "登录"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
