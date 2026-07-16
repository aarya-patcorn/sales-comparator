import { Pencil, Plus, RefreshCw, Trash2, UserCog } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { EmptyState } from "../components/empty-state";
import { Loader } from "../components/loader";
import { PageHeader } from "../components/page-header";
import { PaginationControls } from "../components/pagination-controls";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { Dialog } from "../components/ui/dialog";
import { Input } from "../components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
import { Spinner } from "../components/ui/spinner";
import { Table, TableWrapper } from "../components/ui/table";
import {
  createUser,
  deleteUser,
  fetchAdminMeta,
  fetchUsers,
  resetUserPassword,
  setUserActive,
  updateUser,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { formatDate } from "../lib/utils";
import type { AdminMeta, AdminUser, CreateUserPayload } from "../types/admin";

type UserFormState = {
  user_id: string;
  name: string;
  email: string;
  role: "RM" | "ADMIN";
  is_active: boolean;
  password: string;
};

const pageSize = 10;

const initialFormState: UserFormState = {
  user_id: "",
  name: "",
  email: "",
  role: "RM",
  is_active: true,
  password: "",
};

function StatusBadge({ active, label }: { active: boolean; label: string }) {
  return (
    <Badge className={active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}>
      {label}
    </Badge>
  );
}

export function UserManagementPage() {
  const { token, user: currentUser } = useAuth();
  const { pushToast } = useToast();
  const [meta, setMeta] = useState<AdminMeta | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [draftSearch, setDraftSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [roleFilter, setRoleFilter] = useState("RM");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [formOpen, setFormOpen] = useState(false);
  const [resetOpen, setResetOpen] = useState(false);
  const [editingUser, setEditingUser] = useState<AdminUser | null>(null);
  const [selectedUser, setSelectedUser] = useState<AdminUser | null>(null);
  const [temporaryPassword, setTemporaryPassword] = useState("");
  const [form, setForm] = useState<UserFormState>(initialFormState);
  const [resetPassword, setResetPassword] = useState("");

  useEffect(() => {
    let alive = true;

    async function loadMeta() {
      if (!token) {
        return;
      }

      try {
        const response = await fetchAdminMeta(token);
        if (alive) {
          setMeta(response);
        }
      } catch {}
    }

    void loadMeta();
    return () => {
      alive = false;
    };
  }, [token]);

  useEffect(() => {
    let alive = true;

    async function loadUsers() {
      if (!token) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const response = await fetchUsers(token, { page, pageSize, search, statusFilter, roleFilter });
        if (alive) {
          setUsers(response.items);
          setTotal(response.total);
        }
      } catch (loadError) {
        if (alive) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load users");
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    void loadUsers();
    return () => {
      alive = false;
    };
  }, [page, roleFilter, search, statusFilter, token]);

  const dialogTitle = useMemo(() => (editingUser ? "Edit user" : "Create user"), [editingUser]);

  function resetFormState(nextUser?: AdminUser | null) {
    if (nextUser) {
      setForm({
        user_id: nextUser.user_id,
        name: nextUser.name,
        email: nextUser.email,
        role: nextUser.role,
        is_active: nextUser.is_active,
        password: "",
      });
      setEditingUser(nextUser);
    } else {
      setForm(initialFormState);
      setEditingUser(null);
    }
    setTemporaryPassword("");
  }

  function openCreateDialog() {
    resetFormState(null);
    setFormOpen(true);
  }

  function openEditDialog(target: AdminUser) {
    resetFormState(target);
    setFormOpen(true);
  }

  async function refreshUsers() {
    if (!token) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetchUsers(token, { page, pageSize, search, statusFilter, roleFilter });
      setUsers(response.items);
      setTotal(response.total);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setSubmitting(true);
    setTemporaryPassword("");
    try {
      if (editingUser) {
        await updateUser(token, editingUser.user_id, {
          user_id: form.user_id,
          name: form.name,
          email: form.email,
          role: form.role,
          is_active: form.is_active,
        });
        pushToast({ tone: "success", title: "User updated", description: `${form.user_id} has been updated.` });
        setFormOpen(false);
      } else {
        const payload: CreateUserPayload = {
          user_id: form.user_id,
          name: form.name,
          email: form.email,
          role: form.role,
          is_active: form.is_active,
        };
        if (form.password.trim()) {
          payload.password = form.password.trim();
        }
        const response = await createUser(token, payload);
        if (response.temporary_password) {
          setTemporaryPassword(response.temporary_password);
        } else {
          setFormOpen(false);
        }
        pushToast({ tone: "success", title: "User created", description: `${form.user_id} has been added.` });
      }
      await refreshUsers();
    } catch (submissionError) {
      pushToast({
        tone: "error",
        title: "Unable to save user",
        description: submissionError instanceof Error ? submissionError.message : "Unknown error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(target: AdminUser, active: boolean) {
    if (!token) {
      return;
    }

    try {
      await setUserActive(token, target.user_id, active);
      await refreshUsers();
      pushToast({
        tone: "success",
        title: active ? "User activated" : "User deactivated",
        description: `${target.user_id} is now ${active ? "active" : "inactive"}.`,
      });
    } catch (toggleError) {
      pushToast({
        tone: "error",
        title: "Status change failed",
        description: toggleError instanceof Error ? toggleError.message : "Unknown error",
      });
    }
  }

  async function handleDelete(target: AdminUser) {
    if (!token) {
      return;
    }

    if (!window.confirm(`Delete user ${target.user_id}?`)) {
      return;
    }

    try {
      await deleteUser(token, target.user_id);
      await refreshUsers();
      pushToast({ tone: "success", title: "User deleted", description: `${target.user_id} has been removed.` });
    } catch (deleteError) {
      pushToast({
        tone: "error",
        title: "Delete failed",
        description: deleteError instanceof Error ? deleteError.message : "Unknown error",
      });
    }
  }

  async function handlePasswordReset(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !selectedUser) {
      return;
    }

    setSubmitting(true);
    setTemporaryPassword("");
    try {
      const response = await resetUserPassword(token, selectedUser.user_id, resetPassword.trim() || undefined);
      if (response.temporary_password) {
        setTemporaryPassword(response.temporary_password);
      } else {
        setResetOpen(false);
      }
      pushToast({
        tone: "success",
        title: "Password reset",
        description: `Password reset completed for ${selectedUser.user_id}.`,
      });
      await refreshUsers();
    } catch (resetError) {
      pushToast({
        tone: "error",
        title: "Password reset failed",
        description: resetError instanceof Error ? resetError.message : "Unknown error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  if (loading && users.length === 0) {
    return <Loader label="Loading users..." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="User Management"
        description="Search, segment, and manage RM and admin accounts from a single responsive workspace."
        actions={
          <>
            <Button variant="outline" size="default" onClick={() => void refreshUsers()} disabled={loading}>
              {loading ? <Spinner className="mr-2 size-4" /> : <RefreshCw className="mr-2 size-4" />}
              Refresh
            </Button>
            <Button onClick={openCreateDialog} className="text-white">
              <Plus className="mr-2 size-4" />
              Add user
            </Button>
          </>
        }
      />

      <Card className="rounded-[28px] border-border/70 bg-card/95 shadow-panel">
        <CardContent className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1.5fr)_220px_220px_180px]">
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Search users</p>
            <Input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Search by user ID, name, or email"
              className="h-10 rounded-2xl bg-background/80"
            />
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Role</p>
            <Select value={roleFilter} onValueChange={(value) => setRoleFilter(value ?? "RM")}>
              <SelectTrigger className="h-10 w-full rounded-2xl bg-background/80">
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                {(meta?.roles ?? ["RM", "ADMIN"]).map((role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Status</p>
            <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value ?? "all")}>
              <SelectTrigger className="h-10 w-full rounded-2xl bg-background/80">
                <SelectValue placeholder="Select status" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                <SelectItem value="active">Active</SelectItem>
                <SelectItem value="inactive">Inactive</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              className="h-10 w-full rounded-2xl text-white"
              onClick={() => {
                setPage(1);
                setSearch(draftSearch.trim());
              }}
            >
              Apply filters
            </Button>
          </div>
        </CardContent>
      </Card>

      {error ? <p className="rounded-2xl bg-destructive/10 px-4 py-3 text-sm text-destructive">{error}</p> : null}

      {users.length === 0 ? (
        <EmptyState
          title="No users found"
          description="Adjust the filters or create a new user to populate this view."
          action={<Button onClick={openCreateDialog}>Create first user</Button>}
        />
      ) : (
        <Card className="relative overflow-hidden rounded-[32px] border-border/70 bg-card/95 shadow-panel">
          {loading ? (
            <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/55 backdrop-blur-[1px]">
              <div className="rounded-full border border-border bg-card px-4 py-2 shadow-sm">
                <Spinner className="size-5 text-primary" />
              </div>
            </div>
          ) : null}

          <CardContent className="p-0">
            <div className="flex items-center justify-between border-b border-border/70 px-5 py-4">
              <div>
                <h2 className="text-lg font-semibold text-foreground">Account directory</h2>
                <p className="text-sm text-muted-foreground">Responsive table on desktop and stacked cards on smaller screens.</p>
              </div>
              <Badge className="rounded-full border-primary/10 bg-primary/10 px-3 py-1 text-primary">{total} total</Badge>
            </div>

            <div className="hidden overflow-x-auto lg:block">
              <Table>
                <thead className="bg-background/80 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  <tr>
                    <th className="px-6 py-4">User</th>
                    <th className="px-6 py-4">Role</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Last login</th>
                    <th className="px-6 py-4">Created</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((target) => (
                    <tr key={target.user_id} className="border-t border-border/70 align-top">
                      <td className="px-6 py-5">
                        <p className="font-semibold text-foreground">{target.name}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{target.user_id}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{target.email || "No email"}</p>
                      </td>
                      <td className="px-6 py-5">
                        <Badge>{target.role}</Badge>
                      </td>
                      <td className="px-6 py-5">
                        <StatusBadge active={target.is_active} label={target.status} />
                        {target.must_change_password ? <p className="mt-2 text-xs font-medium uppercase tracking-[0.14em] text-amber-700">Must change password</p> : null}
                      </td>
                      <td className="px-6 py-5 text-sm text-muted-foreground">{formatDate(target.last_login_at)}</td>
                      <td className="px-6 py-5 text-sm text-muted-foreground">{formatDate(target.created_at)}</td>
                      <td className="px-6 py-5">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => openEditDialog(target)}>
                            <Pencil className="mr-2 size-4" />
                            Edit
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedUser(target);
                              setResetPassword("");
                              setTemporaryPassword("");
                              setResetOpen(true);
                            }}
                          >
                            <UserCog className="mr-2 size-4" />
                            Reset
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => void handleToggleActive(target, !target.is_active)}>
                            {target.is_active ? "Deactivate" : "Activate"}
                          </Button>
                          <Button variant="destructive" size="sm" disabled={target.user_id === currentUser?.user_id} onClick={() => void handleDelete(target)}>
                            <Trash2 className="mr-2 size-4" />
                            Delete
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </div>

            <div className="grid gap-4 p-4 lg:hidden">
              {users.map((target) => (
                <div key={target.user_id} className="rounded-3xl border border-border/70 bg-background/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-foreground">{target.name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{target.user_id}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{target.email || "No email"}</p>
                    </div>
                    <Badge>{target.role}</Badge>
                  </div>
                  <div className="mt-4 flex items-center justify-between gap-3">
                    <StatusBadge active={target.is_active} label={target.status} />
                    <p className="text-xs text-muted-foreground">{formatDate(target.last_login_at)}</p>
                  </div>
                  {target.must_change_password ? <p className="mt-3 text-xs font-medium uppercase tracking-[0.14em] text-amber-700">Must change password</p> : null}
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(target)}>
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setSelectedUser(target);
                        setResetPassword("");
                        setTemporaryPassword("");
                        setResetOpen(true);
                      }}
                    >
                      <UserCog className="mr-2 size-4" />
                      Reset
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void handleToggleActive(target, !target.is_active)}>
                      {target.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button variant="destructive" size="sm" disabled={target.user_id === currentUser?.user_id} onClick={() => void handleDelete(target)}>
                      <Trash2 className="mr-2 size-4" />
                      Delete
                    </Button>
                  </div>
                </div>
              ))}
            </div>

            <PaginationControls page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
          </CardContent>
        </Card>
      )}

      <Dialog
        open={formOpen}
        title={dialogTitle}
        description="Fields map directly to the backend admin user request model."
        onClose={() => setFormOpen(false)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="user-form" disabled={submitting} className="text-white">
              {submitting ? <Spinner className="mr-2 size-4" /> : null}
              {submitting ? "Saving..." : editingUser ? "Save changes" : "Create user"}
            </Button>
          </div>
        }
      >
        <form id="user-form" className="grid gap-4 md:grid-cols-2" onSubmit={handleSaveUser}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">User ID</label>
            <Input value={form.user_id} onChange={(event) => setForm((current) => ({ ...current, user_id: event.target.value }))} className="h-10 rounded-2xl" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Name</label>
            <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} className="h-10 rounded-2xl" required />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Email</label>
            <Input type="email" value={form.email} onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))} className="h-10 rounded-2xl" />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">Role</label>
            <Select value={form.role} onValueChange={(value) => setForm((current) => ({ ...current, role: (value ?? "RM") as "RM" | "ADMIN" }))}>
              <SelectTrigger className="h-10 w-full rounded-2xl">
                <SelectValue placeholder="Select role" />
              </SelectTrigger>
              <SelectContent>
                {(meta?.roles ?? ["RM", "ADMIN"]).map((role) => (
                  <SelectItem key={role} value={role}>
                    {role}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {!editingUser ? (
            <div className="space-y-2 md:col-span-2">
              <label className="text-sm font-medium text-foreground">Password</label>
              <Input
                type="password"
                value={form.password}
                onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
                className="h-10 rounded-2xl"
                placeholder="Leave empty to generate a temporary password"
              />
            </div>
          ) : null}
          <label className="flex items-center gap-3 rounded-2xl bg-background px-4 py-3 md:col-span-2">
            <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} />
            <span className="text-sm font-medium text-foreground">User is active</span>
          </label>
          {temporaryPassword ? (
            <div className="rounded-2xl bg-accent/15 px-4 py-3 text-sm text-foreground md:col-span-2">
              Temporary password: <span className="font-semibold">{temporaryPassword}</span>
            </div>
          ) : null}
        </form>
      </Dialog>

      <Dialog
        open={resetOpen}
        title={`Reset password for ${selectedUser?.user_id ?? ""}`}
        description="Leave the field empty to generate a backend-managed temporary password."
        onClose={() => setResetOpen(false)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setResetOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="reset-form" disabled={submitting}>
              {submitting ? <Spinner className="mr-2 size-4" /> : null}
              {submitting ? "Resetting..." : "Reset password"}
            </Button>
          </div>
        }
      >
        <form id="reset-form" className="space-y-4" onSubmit={handlePasswordReset}>
          <div className="space-y-2">
            <label className="text-sm font-medium text-foreground">New password</label>
            <Input type="password" value={resetPassword} onChange={(event) => setResetPassword(event.target.value)} className="h-10 rounded-2xl" placeholder="Leave blank to auto-generate" />
          </div>
          {temporaryPassword ? (
            <div className="rounded-2xl bg-accent/15 px-4 py-3 text-sm text-foreground">
              Temporary password: <span className="font-semibold">{temporaryPassword}</span>
            </div>
          ) : null}
        </form>
      </Dialog>
    </div>
  );
}

