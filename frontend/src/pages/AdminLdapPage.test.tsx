import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi, beforeEach } from "vitest";

import { AdminLdapPage } from "./AdminLdapPage";

// ---------------------------------------------------------------------------
// Mock @/lib/auth so components never need a real AuthProvider or fetch.
// ---------------------------------------------------------------------------

const mockApiCall = vi.fn();

vi.mock("@/lib/auth", () => ({
  useAuth: () => ({
    apiCall: mockApiCall,
    user: { user_id: "u1", email: "admin@test.com", display_name: "Admin", permissions: ["manageConfig"] },
    permissions: new Set(["manageConfig"]),
  }),
  AuthContext: { Provider: ({ children }: { children: React.ReactNode }) => children },
}));

// ---------------------------------------------------------------------------
// Shared fixture — matches LdapProviderOut (all fields)
// ---------------------------------------------------------------------------

const PROVIDER_1 = {
  id: "p1",
  name: "corp-ad",
  server_uris: ["ldaps://dc01:636"],
  bind_dn: "cn=svc,dc=corp,dc=com",
  base_dn: "dc=corp,dc=com",
  enabled: true,
  priority: 10,
  tls_required: true,
  allow_insecure: false,
  user_search_filter: "(mail={input})",
  user_id_attr: "sAMAccountName",
  user_email_attr: "mail",
  user_display_name_attr: "displayName",
  group_membership_attr: "memberOf",
  timeout_seconds: 5,
};

// Org + profile lists (returned by /v1/organizations and /v1/profiles when
// the mappings panel mounts)
const ORGS = [{ id: "org1", name: "ACME Corp" }];
const PROFILES = [{ id: "prof1", name: "Analyst" }];

// Helper: seed the first mockApiCall response with the provider list + empty
// mappings count fan-out, then fall through for subsequent calls.
function seedProviderList(providers = [PROVIDER_1]) {
  // Initial GET /v1/admin/ldap-providers
  mockApiCall.mockResolvedValueOnce(providers);
  // Fan-out: one GET /{id}/mappings per provider for count
  providers.forEach(() => mockApiCall.mockResolvedValueOnce([]));
  // Fallback for any subsequent calls
  mockApiCall.mockResolvedValue([]);
}

describe("AdminLdapPage", () => {
  beforeEach(() => {
    mockApiCall.mockReset();
  });

  // -------------------------------------------------------------------------
  // 1. List renders
  // -------------------------------------------------------------------------

  it("lists providers fetched from the API", async () => {
    seedProviderList();
    render(<AdminLdapPage />);
    await waitFor(() =>
      expect(screen.getByTestId("provider-row-corp-ad")).toBeInTheDocument(),
    );
    expect(screen.getByText("corp-ad")).toBeInTheDocument();
    expect(screen.getByText("ldaps://dc01:636")).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // 2. Test-connection button — OK
  // -------------------------------------------------------------------------

  it("Test button shows OK result inline", async () => {
    mockApiCall
      .mockResolvedValueOnce([PROVIDER_1]) // initial list
      .mockResolvedValueOnce([])           // fan-out mappings count p1
      .mockResolvedValueOnce({             // test-connection POST
        ok: true,
        server_uri_used: "ldaps://dc01:636",
        error: null,
        duration_ms: 42,
      });

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    await userEvent.click(
      screen.getByRole("button", { name: /test connection for corp-ad/i }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("test-result-corp-ad")).toHaveTextContent("OK"),
    );
  });

  // -------------------------------------------------------------------------
  // 3. Test-connection button — error
  // -------------------------------------------------------------------------

  it("Test button shows error result inline on failure", async () => {
    mockApiCall
      .mockResolvedValueOnce([PROVIDER_1])
      .mockResolvedValueOnce([])           // fan-out mappings count
      .mockResolvedValueOnce({
        ok: false,
        server_uri_used: null,
        error: "connection refused",
        duration_ms: 1000,
      });

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    await userEvent.click(
      screen.getByRole("button", { name: /test connection for corp-ad/i }),
    );
    await waitFor(() =>
      expect(screen.getByTestId("test-result-corp-ad")).toHaveTextContent(
        "connection refused",
      ),
    );
  });

  // -------------------------------------------------------------------------
  // 4. Create-provider form submit (POST)
  // -------------------------------------------------------------------------

  it("Create form submits a POST and closes the drawer on success", async () => {
    // Initial empty list + no fan-out (no providers)
    mockApiCall.mockResolvedValueOnce([]);
    // POST /v1/admin/ldap-providers → new provider
    mockApiCall.mockResolvedValueOnce(PROVIDER_1);
    // Refresh after save: list + fan-out count
    mockApiCall.mockResolvedValueOnce([PROVIDER_1]);
    mockApiCall.mockResolvedValueOnce([]); // mappings count for p1

    render(<AdminLdapPage />);
    // Wait for initial render (empty list)
    await screen.findByText("No LDAP providers configured.");

    await userEvent.click(screen.getByText("Add provider"));
    expect(screen.getByTestId("provider-drawer")).toBeInTheDocument();

    // Fill required fields
    await userEvent.type(screen.getByLabelText(/^Name/), "corp-ad");
    await userEvent.type(
      screen.getByLabelText(/Server URIs/),
      "ldaps://dc01:636",
    );
    await userEvent.type(
      screen.getByLabelText(/Bind DN/),
      "cn=svc,dc=corp,dc=com",
    );
    await userEvent.type(screen.getByLabelText(/Bind password/), "s3cr3t");
    await userEvent.type(screen.getByLabelText(/Base DN/), "dc=corp,dc=com");

    await userEvent.click(screen.getByText("Create"));

    // Drawer should close after successful save
    await waitFor(() =>
      expect(screen.queryByTestId("provider-drawer")).not.toBeInTheDocument(),
    );

    // apiCall was called with POST
    expect(mockApiCall).toHaveBeenCalledWith(
      "/v1/admin/ldap-providers",
      expect.objectContaining({ method: "POST" }),
    );
  });

  // -------------------------------------------------------------------------
  // 5. Mapping add / delete
  // -------------------------------------------------------------------------

  it("adds a mapping via POST and deletes it via DELETE", async () => {
    const mapping = {
      id: "m1",
      ldap_provider_id: "p1",
      group_dn: "CN=IR,DC=corp,DC=com",
      organization_id: "org1",
      profile_id: "prof1",
    };

    mockApiCall
      .mockResolvedValueOnce([PROVIDER_1]) // initial provider list
      .mockResolvedValueOnce([])          // fan-out: GET mappings count p1
      .mockResolvedValueOnce([])          // GET mappings (expand)
      .mockResolvedValueOnce(ORGS)        // GET /v1/organizations
      .mockResolvedValueOnce(PROFILES)    // GET /v1/profiles
      .mockResolvedValueOnce(mapping)     // POST mapping
      .mockResolvedValueOnce([mapping])   // GET mappings (refresh after add)
      .mockResolvedValueOnce(undefined)   // DELETE mapping
      .mockResolvedValueOnce([]);         // GET mappings (refresh after delete)

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    // Expand mappings
    await userEvent.click(screen.getByLabelText("Mappings for corp-ad"));
    await screen.findByTestId("add-mapping-form");

    // Fill add-mapping form
    await userEvent.type(
      screen.getByLabelText("Group DN"),
      "CN=IR,DC=corp,DC=com",
    );
    await userEvent.selectOptions(
      screen.getByLabelText("Organization"),
      "org1",
    );
    await userEvent.selectOptions(screen.getByLabelText("Profile"), "prof1");

    await userEvent.click(screen.getByLabelText("Add mapping"));

    // POST should have been called
    await waitFor(() =>
      expect(mockApiCall).toHaveBeenCalledWith(
        "/v1/admin/ldap-providers/p1/mappings",
        expect.objectContaining({ method: "POST" }),
      ),
    );

    // Mapping row appears after refresh
    await screen.findByTestId("mapping-row-m1");

    // Delete mapping
    await userEvent.click(
      screen.getByLabelText("Delete mapping CN=IR,DC=corp,DC=com"),
    );
    await waitFor(() =>
      expect(mockApiCall).toHaveBeenCalledWith(
        "/v1/admin/ldap-providers/p1/mappings/m1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  // -------------------------------------------------------------------------
  // 6. Soft-delete — inline M3 confirm panel flow
  // -------------------------------------------------------------------------

  it("soft-delete calls DELETE after inline confirm panel is confirmed", async () => {
    seedProviderList();
    // Refresh after delete: empty list + no fan-out
    mockApiCall.mockResolvedValueOnce([]);

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    // Click Delete — should show the confirmation panel, not call DELETE yet
    await userEvent.click(screen.getByLabelText("Delete corp-ad"));

    expect(screen.getByTestId("delete-confirm-panel")).toBeInTheDocument();
    expect(screen.getByText(/Soft-delete provider/i)).toBeInTheDocument();

    // Confirm the deletion
    await userEvent.click(screen.getByTestId("delete-confirm-button"));

    await waitFor(() =>
      expect(mockApiCall).toHaveBeenCalledWith(
        "/v1/admin/ldap-providers/p1",
        expect.objectContaining({ method: "DELETE" }),
      ),
    );
  });

  // -------------------------------------------------------------------------
  // 7. Advanced drawer fields are rendered and pre-populated
  // -------------------------------------------------------------------------

  it("test_edit_drawer_renders_advanced_fields: opens drawer, shows advanced fields pre-populated", async () => {
    seedProviderList();

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    // Open Edit drawer for existing provider
    await userEvent.click(screen.getByText("Edit"));
    expect(screen.getByTestId("provider-drawer")).toBeInTheDocument();

    // Open the Advanced section
    await userEvent.click(screen.getByTestId("advanced-section-toggle"));

    // All 6 advanced inputs should be present and pre-populated
    const filterInput = screen.getByLabelText(/User search filter/i);
    expect(filterInput).toBeInTheDocument();
    expect(filterInput).toHaveValue(PROVIDER_1.user_search_filter);

    const idAttrInput = screen.getByLabelText(/User ID attribute/i);
    expect(idAttrInput).toBeInTheDocument();
    expect(idAttrInput).toHaveValue(PROVIDER_1.user_id_attr);

    const emailAttrInput = screen.getByLabelText(/User email attribute/i);
    expect(emailAttrInput).toBeInTheDocument();
    expect(emailAttrInput).toHaveValue(PROVIDER_1.user_email_attr);

    const displayNameAttrInput = screen.getByLabelText(/User display name attribute/i);
    expect(displayNameAttrInput).toBeInTheDocument();
    expect(displayNameAttrInput).toHaveValue(PROVIDER_1.user_display_name_attr);

    const groupMembershipAttrInput = screen.getByLabelText(/Group membership attribute/i);
    expect(groupMembershipAttrInput).toBeInTheDocument();
    expect(groupMembershipAttrInput).toHaveValue(PROVIDER_1.group_membership_attr);

    const timeoutInput = screen.getByLabelText(/Timeout \(seconds\)/i);
    expect(timeoutInput).toBeInTheDocument();
    expect(timeoutInput).toHaveValue(PROVIDER_1.timeout_seconds);
  });

  // -------------------------------------------------------------------------
  // 8. Mappings count is displayed in the provider table
  // -------------------------------------------------------------------------

  it("test_mappings_count_displayed_in_table: shows count from fan-out fetch", async () => {
    const mapping1 = { id: "m1", ldap_provider_id: "p1", group_dn: "CN=A,DC=corp,DC=com", organization_id: "org1", profile_id: "prof1" };
    const mapping2 = { id: "m2", ldap_provider_id: "p1", group_dn: "CN=B,DC=corp,DC=com", organization_id: "org1", profile_id: "prof1" };
    const mapping3 = { id: "m3", ldap_provider_id: "p1", group_dn: "CN=C,DC=corp,DC=com", organization_id: "org1", profile_id: "prof1" };

    mockApiCall
      .mockResolvedValueOnce([PROVIDER_1])                    // GET /v1/admin/ldap-providers
      .mockResolvedValueOnce([mapping1, mapping2, mapping3]); // fan-out: GET p1/mappings

    render(<AdminLdapPage />);
    await screen.findByTestId("provider-row-corp-ad");

    // The mapping count cell should show "3"
    await waitFor(() =>
      expect(screen.getByTestId("mapping-count-p1")).toHaveTextContent("3"),
    );
  });
});
