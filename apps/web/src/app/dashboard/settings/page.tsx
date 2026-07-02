"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Loader2, Save, Shield } from "lucide-react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/store";
import type { User } from "@/lib/types";

export default function SettingsPage() {
  const { user: authUser, setUser } = useAuth();
  const [profile, setProfile] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  // Profile form
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");

  // Password form
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  useEffect(() => {
    api
      .me()
      .then((res) => {
        setProfile(res.data);
        setFullName(res.data.full_name ?? "");
        setEmail(res.data.email);
      })
      .catch((err) => {
        toast.error(err instanceof Error ? err.message : "Failed to load profile");
      })
      .finally(() => setLoading(false));
  }, []);

  async function saveProfile(e: React.FormEvent) {
    e.preventDefault();
    setSavingProfile(true);
    try {
      const res = await api.updateProfile({
        full_name: fullName || undefined,
        email: email || undefined,
      });
      setProfile(res.data);
      setUser(res.data);
      toast.success("Profile updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSavingProfile(false);
    }
  }

  async function savePassword(e: React.FormEvent) {
    e.preventDefault();
    if (newPassword !== confirmPassword) {
      toast.error("Passwords don't match");
      return;
    }
    if (newPassword.length < 8) {
      toast.error("Password must be at least 8 characters");
      return;
    }
    setSavingPassword(true);
    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success("Password changed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setSavingPassword(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 size={20} className="animate-spin text-ink-mute" />
      </div>
    );
  }

  return (
    <div className="space-y-12 animate-fade-up max-w-2xl">
      <header>
        <p className="status text-ink-mute mb-3">
          <span className="status-dot bg-ember" /> account settings
        </p>
        <h1 className="display text-display-lg">Settings</h1>
        <p className="text-ink-mute mt-2">
          Manage your profile and account security.
        </p>
      </header>

      {/* Profile Section */}
      <section className="border-t border-line pt-8">
        <h2 className="display text-display-md mb-6">Profile</h2>
        <form onSubmit={saveProfile} className="space-y-6">
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              Full name
            </label>
            <input
              type="text"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Your name"
              className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
            />
          </div>
          <div className="flex items-center gap-4 pt-2">
            <button
              type="submit"
              disabled={savingProfile}
              className="btn-solid inline-flex items-center gap-2"
            >
              {savingProfile ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Save size={14} />
              )}
              Save profile
            </button>
          </div>
        </form>
      </section>

      {/* Password Section */}
      <section className="border-t border-line pt-8">
        <h2 className="display text-display-md mb-2">Password</h2>
        <p className="text-ink-mute text-sm mb-6">
          Change your account password. You&apos;ll need to enter your current password.
        </p>
        <form onSubmit={savePassword} className="space-y-6">
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              Current password
            </label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
              autoComplete="current-password"
              className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              New password
            </label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
            />
          </div>
          <div>
            <label className="block text-xs font-mono uppercase tracking-wider text-ink-mute mb-2">
              Confirm new password
            </label>
            <input
              type="password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              className="w-full bg-transparent border-0 border-b border-ink/30 px-0 py-3 text-sm focus:outline-none focus:border-ember transition-colors"
            />
          </div>
          <div className="flex items-center gap-4 pt-2">
            <button
              type="submit"
              disabled={savingPassword}
              className="btn-solid inline-flex items-center gap-2"
            >
              {savingPassword ? (
                <Loader2 size={14} className="animate-spin" />
              ) : (
                <Shield size={14} />
              )}
              Change password
            </button>
          </div>
        </form>
      </section>

      {/* Account Info */}
      <section className="border-t border-line pt-8">
        <h2 className="display text-display-md mb-6">Account</h2>
        <dl className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <dt className="text-xs font-mono uppercase tracking-wider text-ink-mute">
              Role
            </dt>
            <dd className="text-sm">{profile?.role ?? "—"}</dd>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <dt className="text-xs font-mono uppercase tracking-wider text-ink-mute">
              Member since
            </dt>
            <dd className="text-sm">
              {profile?.created_at
                ? new Date(profile.created_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                  })
                : "—"}
            </dd>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <dt className="text-xs font-mono uppercase tracking-wider text-ink-mute">
              User ID
            </dt>
            <dd className="text-sm font-mono text-ink-mute text-xs">
              {profile?.id ?? "—"}
            </dd>
          </div>
        </dl>
      </section>
    </div>
  );
}
