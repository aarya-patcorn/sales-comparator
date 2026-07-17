import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Label } from "../components/ui/label";
import { getApiConfigurationError } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";

export function LoginPage() {
  const { isAuthenticated, login, loading } = useAuth();
  const [userId, setUserId] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { pushToast } = useToast();
  const configError = getApiConfigurationError();

  if (!loading && isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSubmitting(true);

    try {
      await login(userId.trim(), password);
      pushToast({ tone: "success", title: "Signed in", description: "Admin session is active." });
      navigate("/dashboard", { replace: true });
    } catch (submissionError) {
      pushToast({ tone: "error", title: "Unable to sign in", description: submissionError instanceof Error ? submissionError.message : "Unable to sign in" });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#F9FAFB] px-4 py-10 text-white sm:px-6">
      <Card className="w-full max-w-md rounded-2xl border-white/10 bg-[#FFFFFF] text-white shadow-2xl shadow-black/30">
        <CardHeader className="space-y-3 px-6 pb-2 pt-8 sm:px-8 sm:pt-10">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#000000]">Admin Login</p>
          <CardTitle className="text-3xl tracking-tight text-black">Sign in to continue</CardTitle>
          <CardDescription className="text-sm leading-6 text-[#8f9aa5]">
            Use the seeded admin credentials configured in the backend.
          </CardDescription>
        </CardHeader>

        <form className="space-y-0" onSubmit={handleSubmit}>
          <CardContent className="space-y-5 px-6 py-7 sm:px-8">
            <div className="space-y-2">
              <Label className="text-[#8f9aa5]" htmlFor="user_id">User ID</Label>
              <Input
                className="h-11 rounded-lg border-grey/10 bg-[#F9FAFB] px-3 text-black placeholder:text-[#65717c] focus-visible:border-[#8da0b0] focus-visible:ring-[#8da0b0]/30"
                id="user_id"
                value={userId}
                onChange={(event) => setUserId(event.target.value)}
                placeholder="admin"
              />
            </div>
            <div className="space-y-2">
              <Label className="text-[#8f9aa5]" htmlFor="password">Password</Label>
              <Input
                className="h-11 rounded-lg border-grey/10 bg-[#F9FAFB] px-3 text-black placeholder:text-[#65717c] focus-visible:border-[#8da0b0] focus-visible:ring-[#8da0b0]/30"
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                placeholder="Enter password"
              />
            </div>

            {configError ? <p className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">{configError}</p> : null}
            {error ? <p className="rounded-lg bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p> : null}
          </CardContent>

          <CardFooter className="px-6 pb-8 sm:px-8 sm:pb-10">
            <Button className="h-11 w-full rounded-lg bg-black border-grey/10 text-[#ffffff] hover:bg-[#e5ebef]" size="lg" type="submit" disabled={submitting || Boolean(configError)}>
              {submitting ? "Signing in..." : "Sign in"}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
