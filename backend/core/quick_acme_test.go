//go:build with_acme && with_quic

package core

import (
	"context"
	"testing"

	"github.com/sagernet/sing-box/option"
)

// Validate the exact fresh-VPS schema against the pinned sing-box version.
// Deliberately do not Start: unit tests must never request real certificates.
func TestQuickInlineACMEConfig(t *testing.T) {
	ctx := Context(context.Background(), InboundRegistry(), OutboundRegistry(),
		EndpointRegistry(), DNSTransportRegistry(), ServiceRegistry(), CertificateProviderRegistry())
	data := []byte(`{
		"inbounds":[{"type":"hysteria2","tag":"quick-test","listen":"127.0.0.1","listen_port":24443,
		"ignore_client_bandwidth":true,"users":[{"name":"quick-test","password":"test-only-password"}],
		"tls":{"enabled":true,"server_name":"proxy.example.com","alpn":["h3"],"min_version":"1.3",
		"certificate_provider":{"type":"acme","domain":["proxy.example.com"],"email":"operator@example.com",
		"provider":"letsencrypt","data_directory":"./certificates/proxy.example.com",
		"disable_http_challenge":false,"disable_tls_alpn_challenge":true}}}],
		"outbounds":[{"type":"direct","tag":"direct"}]
	}`)
	var opts option.Options
	if err := opts.UnmarshalJSONContext(ctx, data); err != nil {
		t.Fatal(err)
	}
	instance, err := NewBox(Options{Context: ctx, Options: opts})
	if err != nil {
		t.Fatal(err)
	}
	defer instance.Close()
}
