import { useEffect, useState, type ReactNode } from "react";
import {
  ClerkProvider,
  SignedIn,
  SignedOut,
  SignIn,
  SignUp,
  useUser,
} from "@clerk/clerk-react";
import { dark } from "@clerk/themes";
import { syncUser } from "@/api/client";

const clerkAppearance = {
  baseTheme: dark,
  variables: {
    colorPrimary: "#3b82f6",
    colorBackground: "#0b1120",
    colorInputBackground: "#1e293b",
    colorInputText: "#f8fafc",
    colorText: "#f8fafc",
    colorTextSecondary: "#94a3b8",
  },
  elements: {
    card: {
      backgroundColor: "#0b1120",
      border: "1px solid #1e293b",
    },
    socialButtonsBlockButton: {
      backgroundColor: "#1e293b",
      color: "#ffffff !important",
      border: "1px solid #334155",
      "&:hover": {
        backgroundColor: "#334155",
        color: "#ffffff !important",
      },
    },
    socialButtonsBlockButtonText: {
      color: "#ffffff !important",
      fontWeight: "500",
    },
    socialButtonsBlockButton__google: {
      color: "#ffffff !important",
    },
    socialButtonsProviderIcon: {
      filter: "none",
    },
    dividerLine: {
      backgroundColor: "#334155",
    },
    dividerText: {
      color: "#94a3b8",
    },
    formFieldLabel: {
      color: "#f8fafc",
    },
    formFieldInput: {
      color: "#f8fafc",
      backgroundColor: "#1e293b",
      borderColor: "#334155",
    },
    footerActionLink: {
      color: "#60a5fa",
      "&:hover": {
        color: "#93c5fd",
      },
    },
  },
};

const CLERK_PUBLISHABLE_KEY =
  import.meta.env.VITE_CLERK_PUBLISHABLE_KEY ||
  (typeof window !== "undefined" ? localStorage.getItem("clerk_pub_key") || "" : "");

function UserSyncEffect() {
  const { user, isLoaded } = useUser();

  useEffect(() => {
    if (isLoaded && user) {
      syncUser({
        id: user.id,
        email: user.primaryEmailAddress?.emailAddress,
        name: user.fullName || user.username || undefined,
        first_name: user.firstName || undefined,
        last_name: user.lastName || undefined,
        image_url: user.imageUrl || undefined,
      }).catch((err) => {
        console.warn("User sync to PostgreSQL failed:", err);
      });
    }
  }, [isLoaded, user]);

  return null;
}

function MissingKeyNotice() {
  const [manualKey, setManualKey] = useState("");

  const handleSave = () => {
    if (manualKey.trim().startsWith("pk_")) {
      localStorage.setItem("clerk_pub_key", manualKey.trim());
      window.location.reload();
    } else {
      alert("Please enter a valid Clerk publishable key starting with pk_test_ or pk_live_");
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-main, #0b0f19)",
        padding: 24,
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: 520,
          width: "100%",
          padding: 32,
          background: "var(--bg-card, #111827)",
          border: "1px solid var(--border, #1f2937)",
          borderRadius: 12,
          boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: 8,
              background: "linear-gradient(135deg, #3b82f6, #06b6d4)",
            }}
          />
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--text-primary, #f3f4f6)", margin: 0 }}>
              Continual RAG
            </h2>
            <p style={{ fontSize: 12, color: "var(--text-muted, #9ca3af)", margin: 0 }}>
              Clerk Authentication Setup
            </p>
          </div>
        </div>

        <p style={{ fontSize: 13, color: "var(--text-secondary, #d1d5db)", lineHeight: 1.6, marginBottom: 20 }}>
          To enable user login and sign-up, paste your <strong>Clerk Publishable Key</strong> in{" "}
          <code style={{ background: "#1f2937", padding: "2px 6px", borderRadius: 4 }}>
            frontend/.env
          </code>
          :
        </p>

        <div
          style={{
            background: "#030712",
            border: "1px solid #1f2937",
            borderRadius: 8,
            padding: "12px 16px",
            fontFamily: "monospace",
            fontSize: 12,
            color: "#38bdf8",
            marginBottom: 24,
          }}
        >
          VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
        </div>

        <div style={{ marginBottom: 16 }}>
          <label style={{ display: "block", fontSize: 12, color: "var(--text-muted)", marginBottom: 8 }}>
            Or paste it here directly to continue immediately:
          </label>
          <input
            type="text"
            placeholder="pk_test_..."
            value={manualKey}
            onChange={(e) => setManualKey(e.target.value)}
            style={{
              width: "100%",
              background: "var(--bg-elevated, #1f2937)",
              border: "1px solid var(--border, #374151)",
              borderRadius: 6,
              color: "#fff",
              padding: "10px 14px",
              fontSize: 13,
              outline: "none",
              marginBottom: 12,
            }}
          />
          <button className="btn btn-primary" style={{ width: "100%" }} onClick={handleSave}>
            Save Key & Continue
          </button>
        </div>
      </div>
    </div>
  );
}

function AuthScreen() {
  const [mode, setMode] = useState<"signin" | "signup">("signin");

  return (
    <div
      style={{
        minHeight: "100vh",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        background: "radial-gradient(ellipse at 50% 20%, #0f172a 0%, #020617 100%)",
        padding: 24,
      }}
    >
      <div style={{ textAlign: "center", marginBottom: 28 }}>
        <div
          style={{
            width: 48,
            height: 48,
            margin: "0 auto 12px",
            borderRadius: 12,
            background: "linear-gradient(135deg, #3b82f6, #06b6d4)",
            boxShadow: "0 0 30px rgba(59, 130, 246, 0.4)",
          }}
        />
        <h1 style={{ fontSize: 24, fontWeight: 700, color: "#f8fafc", letterSpacing: "-0.02em", margin: 0 }}>
          Continual RAG
        </h1>
        <p style={{ fontSize: 13, color: "#94a3b8", marginTop: 4, letterSpacing: "0.02em" }}>
          News Intelligence & Continual Research Assistant
        </p>
      </div>

      <div style={{ marginBottom: 16, display: "flex", gap: 8 }}>
        <button
          className={`btn btn-sm ${mode === "signin" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setMode("signin")}
        >
          Sign In
        </button>
        <button
          className={`btn btn-sm ${mode === "signup" ? "btn-primary" : "btn-ghost"}`}
          onClick={() => setMode("signup")}
        >
          Sign Up
        </button>
      </div>

      <div style={{ minHeight: 450 }}>
        {mode === "signin" ? (
          <SignIn
            routing="hash"
            appearance={clerkAppearance}
          />
        ) : (
          <SignUp
            routing="hash"
            appearance={clerkAppearance}
          />
        )}
      </div>
    </div>
  );
}

export default function AuthGate({ children }: { children: ReactNode }) {
  const isKeyMissing =
    !CLERK_PUBLISHABLE_KEY ||
    CLERK_PUBLISHABLE_KEY.includes("YOUR_CLERK_PUBLISHABLE_KEY_HERE");

  if (isKeyMissing) {
    return <MissingKeyNotice />;
  }

  return (
    <ClerkProvider publishableKey={CLERK_PUBLISHABLE_KEY} appearance={clerkAppearance}>
      <SignedIn>
        <UserSyncEffect />
        {children}
      </SignedIn>
      <SignedOut>
        <AuthScreen />
      </SignedOut>
    </ClerkProvider>
  );
}
