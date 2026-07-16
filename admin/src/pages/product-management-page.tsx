import { Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
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
import { Table } from "../components/ui/table";
import { Textarea } from "../components/ui/textarea";
import {
  createProduct,
  deleteProduct,
  fetchAdminMeta,
  fetchProducts,
  setProductActive,
  updateProduct,
} from "../lib/api";
import { useAuth } from "../lib/auth";
import { useToast } from "../lib/toast";
import { formatDate } from "../lib/utils";
import type { AdminMeta, ProductPayload, ProductRecord } from "../types/admin";

type ProductFormState = ProductPayload;
type ProductFormMode = "add" | "edit";

const pageSize = 10;

const initialProductForm: ProductFormState = {
  code: "",
  name: "",
  is_type: "",
  en_type: "",
  tagline: "",
  description: "",
  max_tile_size: "",
  areas: [],
  params: {},
  is_active: true,
};

function createEmptyProductForm(productParamKeys: string[]): ProductFormState {
  return {
    ...initialProductForm,
    areas: [],
    params: Object.fromEntries(productParamKeys.map((key) => [key, ""])),
  };
}

function createEditProductForm(target: ProductRecord, productParamKeys: string[]): ProductFormState {
  return {
    code: target.code,
    name: target.name,
    is_type: target.is_type,
    en_type: target.en_type,
    tagline: target.tagline,
    description: target.description,
    max_tile_size: target.max_tile_size,
    areas: [...target.areas],
    params: {
      ...Object.fromEntries(productParamKeys.map((key) => [key, ""])),
      ...target.params,
    },
    is_active: target.is_active,
  };
}

function ProductFormFields({
  form,
  setForm,
  meta,
}: {
  form: ProductFormState;
  setForm: React.Dispatch<React.SetStateAction<ProductFormState>>;
  meta: AdminMeta | null;
}) {
  const productParamKeys = meta?.product_param_keys ?? [];

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">Code</label>
        <Input value={form.code} onChange={(event) => setForm((current) => ({ ...current, code: event.target.value }))} className="h-10 rounded-2xl" required />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">Name</label>
        <Input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} className="h-10 rounded-2xl" required />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">IS Type</label>
        <Input value={form.is_type} onChange={(event) => setForm((current) => ({ ...current, is_type: event.target.value }))} className="h-10 rounded-2xl" />
      </div>
      <div className="space-y-2">
        <label className="text-sm font-medium text-foreground">EN Type</label>
        <Input value={form.en_type} onChange={(event) => setForm((current) => ({ ...current, en_type: event.target.value }))} className="h-10 rounded-2xl" />
      </div>
      <div className="space-y-2 lg:col-span-2">
        <label className="text-sm font-medium text-foreground">Tagline</label>
        <Input value={form.tagline} onChange={(event) => setForm((current) => ({ ...current, tagline: event.target.value }))} className="h-10 rounded-2xl" />
      </div>
      <div className="space-y-2 lg:col-span-2">
        <label className="text-sm font-medium text-foreground">Description</label>
        <Textarea value={form.description} onChange={(event) => setForm((current) => ({ ...current, description: event.target.value }))} className="rounded-3xl" />
      </div>
      <div className="space-y-2 lg:col-span-2">
        <label className="text-sm font-medium text-foreground">Max tile size</label>
        <Input value={form.max_tile_size} onChange={(event) => setForm((current) => ({ ...current, max_tile_size: event.target.value }))} className="h-10 rounded-2xl" />
      </div>
      <div className="space-y-3 lg:col-span-2">
        <label className="text-sm font-medium text-foreground">Areas</label>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {(meta?.areas ?? []).map((area) => {
            const checked = form.areas.includes(area);
            return (
              <label key={area} className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/80 px-4 py-3 text-sm text-foreground">
                <input
                  type="checkbox"
                  checked={checked}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      areas: event.target.checked
                        ? [...current.areas, area]
                        : current.areas.filter((value) => value !== area),
                    }))
                  }
                />
                <span>{area}</span>
              </label>
            );
          })}
        </div>
      </div>
      <div className="space-y-3 lg:col-span-2">
        <label className="text-sm font-medium text-foreground">Performance parameters</label>
        <div className="grid gap-4 md:grid-cols-2">
          {productParamKeys.map((key) => (
            <div key={key} className="space-y-2">
              <label className="text-sm text-muted-foreground">{key}</label>
              <Input
                value={form.params[key] ?? ""}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    params: {
                      ...current.params,
                      [key]: event.target.value,
                    },
                  }))
                }
                className="h-10 rounded-2xl"
                placeholder={`Value for ${key}`}
              />
            </div>
          ))}
        </div>
      </div>
      <label className="flex items-center gap-3 rounded-2xl border border-border/70 bg-background/80 px-4 py-3 lg:col-span-2">
        <input type="checkbox" checked={form.is_active} onChange={(event) => setForm((current) => ({ ...current, is_active: event.target.checked }))} />
        <span className="text-sm font-medium text-foreground">Product is active</span>
      </label>
    </div>
  );
}

export function ProductManagementPage() {
  const { token } = useAuth();
  const { pushToast } = useToast();
  const [meta, setMeta] = useState<AdminMeta | null>(null);
  const [products, setProducts] = useState<ProductRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [draftSearch, setDraftSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [areaFilter, setAreaFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [formMode, setFormMode] = useState<ProductFormMode | null>(null);
  const [selectedProduct, setSelectedProduct] = useState<ProductRecord | null>(null);
  const [formSession, setFormSession] = useState(0);
  const [form, setForm] = useState<ProductFormState>(initialProductForm);
  const [createOpen, setCreateOpen] = useState(false);

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

    async function loadProducts() {
      if (!token) {
        return;
      }

      setLoading(true);
      setError("");
      try {
        const response = await fetchProducts(token, { page, pageSize, search, statusFilter, areaFilter });
        if (alive) {
          setProducts(response.items);
          setTotal(response.total);
        }
      } catch (loadError) {
        if (alive) {
          setError(loadError instanceof Error ? loadError.message : "Unable to load products");
        }
      } finally {
        if (alive) {
          setLoading(false);
        }
      }
    }

    void loadProducts();
    return () => {
      alive = false;
    };
  }, [areaFilter, page, search, statusFilter, token]);

  const dialogTitle = useMemo(() => (selectedProduct ? `Edit ${selectedProduct.code}` : "Edit product"), [selectedProduct]);
  const productParamKeys = meta?.product_param_keys ?? [];

  function resetProductEditor() {
    setFormMode(null);
    setSelectedProduct(null);
    setCreateOpen(false);
    setForm(createEmptyProductForm(productParamKeys));
    setFormSession((current) => current + 1);
  }

  function openCreateDialog() {
    setSelectedProduct(null);
    setForm(createEmptyProductForm(productParamKeys));
    setFormSession((current) => current + 1);
    setFormMode("add");
    setCreateOpen(true);
  }

  function openEditDialog(target: ProductRecord) {
    setSelectedProduct(target);
    setForm(createEditProductForm(target, productParamKeys));
    setFormSession((current) => current + 1);
    setFormMode("edit");
  }

  async function refreshProducts() {
    if (!token) {
      return;
    }

    setLoading(true);
    try {
      const response = await fetchProducts(token, { page, pageSize, search, statusFilter, areaFilter });
      setProducts(response.items);
      setTotal(response.total);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveProduct(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) {
      return;
    }

    setSubmitting(true);
    try {
      const payload: ProductPayload = {
        ...form,
        params: Object.fromEntries(Object.entries(form.params).filter(([, value]) => value.trim())),
      };
      if (formMode === "edit" && selectedProduct) {
        await updateProduct(token, selectedProduct.code, payload);
        pushToast({ tone: "success", title: "Product updated", description: `${payload.code} has been updated.` });
      } else if (formMode === "add") {
        await createProduct(token, payload);
        pushToast({ tone: "success", title: "Product created", description: `${payload.code} has been added.` });
      } else {
        return;
      }
      resetProductEditor();
      await refreshProducts();
    } catch (submissionError) {
      pushToast({
        tone: "error",
        title: "Unable to save product",
        description: submissionError instanceof Error ? submissionError.message : "Unknown error",
      });
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggleActive(target: ProductRecord, active: boolean) {
    if (!token) {
      return;
    }

    try {
      await setProductActive(token, target.code, active);
      await refreshProducts();
      pushToast({
        tone: "success",
        title: active ? "Product activated" : "Product deactivated",
        description: `${target.code} is now ${active ? "active" : "inactive"}.`,
      });
    } catch (toggleError) {
      pushToast({
        tone: "error",
        title: "Status change failed",
        description: toggleError instanceof Error ? toggleError.message : "Unknown error",
      });
    }
  }

  async function handleDelete(target: ProductRecord) {
    if (!token) {
      return;
    }

    if (!window.confirm(`Delete product ${target.code}?`)) {
      return;
    }

    try {
      await deleteProduct(token, target.code);
      await refreshProducts();
      pushToast({ tone: "success", title: "Product deleted", description: `${target.code} has been removed.` });
    } catch (deleteError) {
      pushToast({
        tone: "error",
        title: "Delete failed",
        description: deleteError instanceof Error ? deleteError.message : "Unknown error",
      });
    }
  }

  if (loading && products.length === 0) {
    return <Loader label="Loading products..." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Product Management"
        description="Filter the catalog, manage active SKUs, and maintain backend-driven product attributes from one panel."
        actions={
          <>
            <Button variant="outline" onClick={() => void refreshProducts()} disabled={loading}>
              {loading ? <Spinner className="mr-2 size-4" /> : <RefreshCw className="mr-2 size-4" />}
              Refresh
            </Button>
            <Button onClick={openCreateDialog} className="text-white">
              <Plus className="mr-2 size-4" />
              Add product
            </Button>
          </>
        }
      />
      <Card className="rounded-[28px] border-border/70 bg-card/95 shadow-panel">
        <CardContent className="grid gap-4 p-5 lg:grid-cols-[minmax(0,1.5fr)_220px_220px_180px]">
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Search catalog</p>
            <Input
              value={draftSearch}
              onChange={(event) => setDraftSearch(event.target.value)}
              placeholder="Search by code, name, or tagline"
              className="h-10 rounded-2xl bg-background/80"
            />
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
          <div className="space-y-2">
            <p className="text-sm font-medium text-foreground">Area</p>
            <Select value={areaFilter} onValueChange={(value) => setAreaFilter(value ?? "all")}>
              <SelectTrigger className="h-10 w-full rounded-2xl bg-background/80">
                <SelectValue placeholder="Select area" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All areas</SelectItem>
                {(meta?.areas ?? []).map((area) => (
                  <SelectItem key={area} value={area}>
                    {area}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex items-end">
            <Button
              className="h-10 text-white w-full rounded-2xl text-white"
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

      {products.length === 0 ? (
        <EmptyState
          title="No products found"
          description="Adjust the filters or create a new product record."
          action={<Button onClick={openCreateDialog}>Create first product</Button>}
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
                <h2 className="text-lg font-semibold text-foreground">Product directory</h2>
                <p className="text-sm text-muted-foreground">Filter card above, responsive list below, and desktop table for full catalog management.</p>
              </div>
              <Badge className="rounded-full border-primary/10 bg-primary/10 px-3 py-1 text-primary">{total} products</Badge>
            </div>

            <div className="hidden overflow-x-auto lg:block">
              <Table>
                <thead className="bg-background/80 text-xs uppercase tracking-[0.18em] text-muted-foreground">
                  <tr>
                    <th className="px-6 py-4">Product</th>
                    <th className="px-6 py-4">Areas</th>
                    <th className="px-6 py-4">Status</th>
                    <th className="px-6 py-4">Source</th>
                    <th className="px-6 py-4">Updated</th>
                    <th className="px-6 py-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {products.map((target) => (
                    <tr key={target.code} className="border-t border-border/70 align-top">
                      <td className="px-6 py-5">
                        <p className="font-semibold text-foreground">{target.code}</p>
                        <p className="mt-1 text-sm text-foreground">{target.name}</p>
                        <p className="mt-1 text-sm text-muted-foreground">{target.tagline || "No tagline"}</p>
                      </td>
                      <td className="px-6 py-5">
                        <div className="flex max-w-sm flex-wrap gap-2">
                          {target.areas.map((area) => (
                            <Badge key={area}>{area}</Badge>
                          ))}
                        </div>
                      </td>
                      <td className="px-6 py-5">
                        <Badge className={target.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}>
                          {target.is_active ? "active" : "inactive"}
                        </Badge>
                      </td>
                      <td className="px-6 py-5 text-sm text-muted-foreground">{target.source}</td>
                      <td className="px-6 py-5 text-sm text-muted-foreground">{formatDate(target.updated_at)}</td>
                      <td className="px-6 py-5">
                        <div className="flex flex-wrap justify-end gap-2">
                          <Button variant="outline" size="sm" onClick={() => openEditDialog(target)}>
                            <Pencil className="mr-2 size-4" />
                            Edit
                          </Button>
                          <Button variant="ghost" size="sm" onClick={() => void handleToggleActive(target, !target.is_active)}>
                            {target.is_active ? "Deactivate" : "Activate"}
                          </Button>
                          <Button variant="destructive" size="sm" onClick={() => void handleDelete(target)}>
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
              {products.map((target) => (
                <div key={target.code} className="rounded-3xl border border-border/70 bg-background/70 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-semibold text-foreground">{target.code}</p>
                      <p className="mt-1 text-sm text-foreground">{target.name}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{target.tagline || "No tagline"}</p>
                    </div>
                    <Badge className={target.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-rose-200 bg-rose-50 text-rose-700"}>
                      {target.is_active ? "active" : "inactive"}
                    </Badge>
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    {target.areas.map((area) => (
                      <Badge key={area}>{area}</Badge>
                    ))}
                  </div>
                  <div className="mt-4 grid gap-2 sm:grid-cols-2">
                    <Button variant="outline" size="sm" onClick={() => openEditDialog(target)}>
                      <Pencil className="mr-2 size-4" />
                      Edit
                    </Button>
                    <Button variant="ghost" size="sm" onClick={() => void handleToggleActive(target, !target.is_active)}>
                      {target.is_active ? "Deactivate" : "Activate"}
                    </Button>
                    <Button variant="destructive" size="sm" onClick={() => void handleDelete(target)}>
                      <Trash2 className="mr-2 size-4" />
                      Delete
                    </Button>
                    <p className="flex items-center justify-end text-xs text-muted-foreground sm:justify-start">Updated {formatDate(target.updated_at)}</p>
                  </div>
                </div>
              ))}
            </div>

            <PaginationControls page={page} pageSize={pageSize} total={total} onPageChange={setPage} />
          </CardContent>
        </Card>
      )}

      <Dialog
        open={createOpen}
        title="Add product"
        description="Fill in the product details to add a new item to the catalog."
        onClose={() => setCreateOpen(false)}
        className="max-w-5xl"
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button type="submit" form="product-create-form" disabled={submitting} className="text-white">
              {submitting ? <Spinner className="mr-2 size-4" /> : null}
              {submitting ? "Saving..." : "Create product"}
            </Button>
          </div>
        }
      >
        <form key={`create-${formSession}`} id="product-create-form" className="space-y-5" onSubmit={handleSaveProduct}>
          <ProductFormFields form={form} setForm={setForm} meta={meta} />
        </form>
      </Dialog>

      <Dialog
        open={formMode === "edit"}
        title={dialogTitle}
        description="This form uses the backend product payload shape, including areas and supported parameter keys."
        onClose={resetProductEditor}
        className="max-w-5xl"
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="ghost" onClick={resetProductEditor}>
              Cancel
            </Button>
            <Button type="submit" form="product-edit-form" disabled={submitting}>
              {submitting ? <Spinner className="mr-2 size-4" /> : null}
              {submitting ? "Saving..." : "Save changes"}
            </Button>
          </div>
        }
      >
        <form key={`edit-${formSession}`} id="product-edit-form" className="space-y-5" onSubmit={handleSaveProduct}>
          <ProductFormFields form={form} setForm={setForm} meta={meta} />
        </form>
      </Dialog>
    </div>
  );
}
