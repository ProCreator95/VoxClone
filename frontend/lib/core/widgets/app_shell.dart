import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../routing/navigation_config.dart';
import 'app_sidebar.dart';

/// Responsive application shell — fixed sidebar on tablet/desktop, drawer on mobile.
class AppShell extends StatefulWidget {
  const AppShell({super.key, required this.child});

  final Widget child;

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final _scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  Widget build(BuildContext context) {
    final path = GoRouterState.of(context).uri.path;
    final width = MediaQuery.sizeOf(context).width;
    final isMobile = width < NavigationConfig.mobileBreakpoint;
    final sidebarWidth = width >= 1024
        ? NavigationConfig.sidebarWidthDesktop
        : NavigationConfig.sidebarWidthTablet;

    if (isMobile) {
      return Scaffold(
        key: _scaffoldKey,
        appBar: AppBar(
          title: Text(NavigationConfig.titleForPath(path) ?? 'VoxClone'),
          leading: IconButton(
            icon: const Icon(Icons.menu_rounded),
            onPressed: () => _scaffoldKey.currentState?.openDrawer(),
          ),
        ),
        drawer: Drawer(
          width: NavigationConfig.sidebarWidthDesktop,
          child: AppSidebar(
            currentPath: path,
            width: NavigationConfig.sidebarWidthDesktop,
            onNavigate: () => Navigator.of(context).pop(),
          ),
        ),
        body: widget.child,
      );
    }

    return Scaffold(
      body: Row(
        children: [
          AppSidebar(currentPath: path, width: sidebarWidth),
          Expanded(child: widget.child),
        ],
      ),
    );
  }
}
