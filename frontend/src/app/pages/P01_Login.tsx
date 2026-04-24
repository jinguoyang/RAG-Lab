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
          <h1 className="text-4xl font-serif text-terracotta mb-2">RAG Platform</h1>
          <p className="text-stone-gray">Enterprise Knowledge Base & Debugging System</p>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Sign In</CardTitle>
          </CardHeader>
          <form onSubmit={handleLogin}>
            <CardContent className="space-y-4">
              {error && (
                <Alert variant="error" title="Authentication Failed">
                  {error}
                </Alert>
              )}
              <Input 
                label="Username or Email" 
                placeholder="admin@example.com"
                required
              />
              <Input 
                label="Password" 
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
                {isLoading ? "Authenticating..." : "Sign In"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  );
}
