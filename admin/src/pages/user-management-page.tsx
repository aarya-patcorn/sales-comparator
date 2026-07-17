import { useEffect, useState } from "react";
import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
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
import {
  createUser,
  deleteUser,
  fetchUsers,
  setUserActive,
  updateUser,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { confirmToast, useToast } from "../lib/toast";
import { formatDate } from "../lib/utils";
import type { AdminUser, CreateUserPayload } from "../types/admin";

type FormState = {
  name: string;
  email: string;
  mobileNumber: string;
  role: "RM";
  is_active: boolean;
};

const blank: FormState = {
  name: "",
  email: "",
  mobileNumber: "",
  role: "RM",
  is_active: true,
};

const pageSize = 10;

export function UserManagementPage() {
  const { token } = useAuth();
  const { pushToast } = useToast();

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [loading, setLoading] = useState(true);

  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<AdminUser | null>(null);
  const [form, setForm] = useState<FormState>(blank);
  const [saving, setSaving] = useState(false);

  async function load() {
    if (!token) return;
    setLoading(true);
    try {
      const response = await fetchUsers(token, {
        page,
        pageSize,
        search,
        statusFilter: status,
        roleFilter: "RM",
      });
      setUsers(response.items);
      setTotal(response.total);
    } catch (error) {
      pushToast({
        tone: "error",
        title: "Unable to load RM users",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [token, page, search, status]);

  function edit(user?: AdminUser) {
    setEditing(user ?? null);
    setForm(
      user
        ? {
            name: user.name,
            email: user.email,
            mobileNumber: user.mobileNumber,
            role: "RM",
            is_active: user.is_active,
          }
        : blank,
    );
    setOpen(true);
  }

  async function save(event: React.FormEvent) {
    event.preventDefault();
    if (!token) return;
    setSaving(true);
    try {
      if (editing) {
        await updateUser(token, editing.mobileNumber, { ...form, role: "RM" });
      } else {
        const payload: CreateUserPayload = { ...form, role: "RM" };
        await createUser(token, payload);
      }
      setOpen(false);
      pushToast({
        tone: "success",
        title: editing ? "RM user updated" : "RM user created",
        description: form.name + " is saved.",
      });
      await load();
    } catch (error) {
      pushToast({
        tone: "error",
        title: "Unable to save RM user",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    } finally {
      setSaving(false);
    }
  }

  async function toggle(user: AdminUser) {
    if (!token) return;
    try {
      await setUserActive(token, user.mobileNumber, !user.is_active);
      await load();
    } catch (error) {
      pushToast({
        tone: "error",
        title: "Status change failed",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  async function remove(user: AdminUser) {
    if (!token || !(await confirmToast(`Delete ${user.name}?`))) return;
    try {
      await deleteUser(token, user.mobileNumber);
      await load();
    } catch (error) {
      pushToast({
        tone: "error",
        title: "Delete failed",
        description: error instanceof Error ? error.message : "Unknown error",
      });
    }
  }

  if (loading && !users.length) {
    return <Loader label="Loading RM users..." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="RM User Management"
        description="Create and maintain RM access using a unique mobile number."
        actions={
          <>
            <Button variant="outline" onClick={() => void load()}>
              <RefreshCw className="mr-2 size-4" />
              Refresh
            </Button>
            <Button onClick={() => edit()} className="text-white">
              <Plus className="mr-2 size-4" />
              Add RM user
            </Button>
          </>
        }
      />

      <Card className="rounded-[28px] border-border/70 bg-card/95 shadow-panel">
        <CardContent className="grid gap-4 p-5 md:grid-cols-[1fr_220px_180px]">
          <Input
            value={search}
            onChange={(e) => {
              setPage(1);
              setSearch(e.target.value);
            }}
            placeholder="Search name, email, or mobile number"
            className="h-10 rounded-2xl"
          />
          <Select
            value={status}
            onValueChange={(v) => {
              setPage(1);
              setStatus(v ?? "all");
            }}
          >
            <SelectTrigger className="h-10 rounded-2xl">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
          <div className="flex items-center text-sm text-muted-foreground">
            {total} RM users
          </div>
        </CardContent>
      </Card>

      <Card className="rounded-[32px] border-border/70 bg-card/95 shadow-panel">
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="bg-background/80 text-xs uppercase tracking-[.18em] text-muted-foreground">
                <tr>
                  <th className="px-6 py-4">Name</th>
                  <th className="px-6 py-4">Email</th>
                  <th className="px-6 py-4">Mobile number</th>
                  <th className="px-6 py-4">Role</th>
                  <th className="px-6 py-4">Status</th>
                  <th className="px-6 py-4">Last login</th>
                  <th className="px-6 py-4 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.mobileNumber} className="border-t border-border/70">
                    <td className="px-6 py-4 font-semibold">{user.name}</td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {user.email || "—"}
                    </td>
                    <td className="px-6 py-4 text-sm">{user.mobileNumber}</td>
                    <td className="px-6 py-4">
                      <Badge>RM</Badge>
                    </td>
                    <td className="px-6 py-4">
                      <Badge>{user.status}</Badge>
                    </td>
                    <td className="px-6 py-4 text-sm text-muted-foreground">
                      {formatDate(user.last_login)}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => edit(user)}>
                          <Pencil className="mr-2 size-4" />
                          Edit
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => void toggle(user)}
                        >
                          {user.is_active ? "Deactivate" : "Activate"}
                        </Button>
                        <Button
                          variant="destructive"
                          size="sm"
                          onClick={() => void remove(user)}
                        >
                          <Trash2 className="mr-2 size-4" />
                          Delete
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <PaginationControls
            page={page}
            pageSize={pageSize}
            total={total}
            onPageChange={setPage}
          />
        </CardContent>
      </Card>

      <Dialog
        open={open}
        title={editing ? "Edit RM user" : "Create RM user"}
        description="Only Name, Email, Mobile Number, Role, and Status are required."
        onClose={() => setOpen(false)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="rm-user-form"
              disabled={saving}
              className="text-white"
            >
              {saving ? <Spinner className="mr-2 size-4" /> : null}
              {editing ? "Save changes" : "Create user"}
            </Button>
          </div>
        }
      >
        <form
          id="rm-user-form"
          className="grid gap-4 md:grid-cols-2"
          onSubmit={save}
        >
          <label className="space-y-2 text-sm font-medium">
            Name
            <Input
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="h-10 rounded-2xl"
            />
          </label>

          <label className="space-y-2 text-sm font-medium">
            Email
            <Input
              type="email"
              value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })}
              className="h-10 rounded-2xl"
            />
          </label>

          <label className="space-y-2 text-sm font-medium">
            Mobile Number
            <Input
              required
              value={form.mobileNumber}
              onChange={(e) =>
                setForm({ ...form, mobileNumber: e.target.value })
              }
              className="h-10 rounded-2xl"
            />
          </label>

          <label className="space-y-2 text-sm font-medium">
            Role
            <Select value="RM" disabled>
              <SelectTrigger className="h-10 rounded-2xl">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="RM">RM</SelectItem>
              </SelectContent>
            </Select>
          </label>

          <label className="flex items-center gap-3 rounded-2xl bg-background px-4 py-3 text-sm font-medium md:col-span-2">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(e) => setForm({ ...form, is_active: e.target.checked })}
            />
            Active
          </label>
        </form>
      </Dialog>
    </div>
  );
}